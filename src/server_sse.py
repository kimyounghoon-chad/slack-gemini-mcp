"""
Slack 메시지 기반 Gemini 챗봇 MCP 서버 (SSE 버전)

Cloud Run에 배포하여 원격 MCP 서버로 사용
HTTP + Server-Sent Events 기반
"""

import os
import logging
from datetime import datetime
from typing import Optional

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
import uvicorn

from slack_service import SlackService
from gemini_service import GeminiService

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 서버 인스턴스 생성
server = Server("slack-gemini-mcp")

# 서비스 인스턴스 (lazy initialization)
_slack_service: Optional[SlackService] = None
_gemini_service: Optional[GeminiService] = None


def get_slack_service() -> SlackService:
    """Slack 서비스 인스턴스 반환 (싱글톤)"""
    global _slack_service
    if _slack_service is None:
        _slack_service = SlackService()
    return _slack_service


def get_gemini_service() -> GeminiService:
    """Gemini 서비스 인스턴스 반환 (싱글톤)"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service


@server.list_tools()
async def list_tools() -> list[Tool]:
    """사용 가능한 도구 목록 반환"""
    return [
        Tool(
            name="list_slack_channels",
            description="Slack 워크스페이스의 채널 목록을 조회합니다.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_slack_messages",
            description="특정 Slack 채널의 최근 메시지를 가져옵니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Slack 채널 ID (예: C01234567)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "가져올 메시지 수 (기본값: 50, 최대: 200)",
                        "default": 50
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="search_slack_messages",
            description="Slack 메시지에서 키워드를 검색합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 키워드"
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "검색할 채널 ID (선택사항, 없으면 전체 검색)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="ask_gemini_about_slack",
            description="Slack 메시지를 컨텍스트로 사용하여 Gemini에게 질문합니다. 특정 채널의 대화 내용을 기반으로 답변을 생성합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Gemini에게 할 질문"
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "컨텍스트로 사용할 Slack 채널 ID"
                    },
                    "message_limit": {
                        "type": "integer",
                        "description": "컨텍스트로 사용할 메시지 수 (기본값: 100)",
                        "default": 100
                    }
                },
                "required": ["question", "channel_id"]
            }
        ),
        Tool(
            name="summarize_slack_channel",
            description="Slack 채널의 최근 대화를 요약합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "요약할 Slack 채널 ID"
                    },
                    "message_limit": {
                        "type": "integer",
                        "description": "요약할 메시지 수 (기본값: 100)",
                        "default": 100
                    }
                },
                "required": ["channel_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """도구 호출 처리"""
    try:
        if name == "list_slack_channels":
            return await handle_list_channels()

        elif name == "get_slack_messages":
            return await handle_get_messages(
                channel_id=arguments["channel_id"],
                limit=arguments.get("limit", 50)
            )

        elif name == "search_slack_messages":
            return await handle_search_messages(
                query=arguments["query"],
                channel_id=arguments.get("channel_id")
            )

        elif name == "ask_gemini_about_slack":
            return await handle_ask_gemini(
                question=arguments["question"],
                channel_id=arguments["channel_id"],
                message_limit=arguments.get("message_limit", 100)
            )

        elif name == "summarize_slack_channel":
            return await handle_summarize_channel(
                channel_id=arguments["channel_id"],
                message_limit=arguments.get("message_limit", 100)
            )

        else:
            return [TextContent(type="text", text=f"알 수 없는 도구: {name}")]

    except Exception as e:
        logger.error(f"도구 실행 오류 ({name}): {e}")
        return [TextContent(type="text", text=f"오류 발생: {str(e)}")]


async def handle_list_channels() -> list[TextContent]:
    """채널 목록 조회 처리"""
    slack = get_slack_service()
    channels = slack.get_channels()

    result = "## Slack 채널 목록\n\n"
    for ch in channels[:50]:  # 상위 50개만 표시
        name = ch.get("name", "unknown")
        channel_id = ch["id"]
        member_count = ch.get("num_members", "?")
        result += f"- **#{name}** (`{channel_id}`) - {member_count}명\n"

    result += f"\n총 {len(channels)}개 채널 (상위 50개 표시)"
    return [TextContent(type="text", text=result)]


async def handle_get_messages(channel_id: str, limit: int) -> list[TextContent]:
    """메시지 조회 처리"""
    slack = get_slack_service()
    messages = slack.get_channel_messages(channel_id, limit=min(limit, 200))

    if not messages:
        return [TextContent(type="text", text="메시지가 없습니다.")]

    result = f"## 채널 메시지 (최근 {len(messages)}개)\n\n"
    for msg in reversed(messages):  # 시간순 정렬
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        ts = msg.get("ts", "")

        # 타임스탬프를 읽기 쉬운 형식으로 변환
        try:
            dt = datetime.fromtimestamp(float(ts))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            time_str = ts

        result += f"**[{time_str}] {user}**: {text}\n\n"

    return [TextContent(type="text", text=result)]


async def handle_search_messages(query: str, channel_id: Optional[str]) -> list[TextContent]:
    """메시지 검색 처리"""
    slack = get_slack_service()

    if channel_id:
        # 특정 채널에서 검색
        messages = slack.get_channel_messages(channel_id, limit=200)
        matches = [
            msg for msg in messages
            if query.lower() in msg.get("text", "").lower()
        ]
    else:
        # 전체 채널에서 검색 (API 검색 사용)
        matches = slack.search_messages(query)

    if not matches:
        return [TextContent(type="text", text=f"'{query}'에 대한 검색 결과가 없습니다.")]

    result = f"## '{query}' 검색 결과 ({len(matches)}개)\n\n"
    for msg in matches[:20]:  # 최대 20개 표시
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        result += f"- **{user}**: {text[:200]}{'...' if len(text) > 200 else ''}\n"

    return [TextContent(type="text", text=result)]


async def handle_ask_gemini(question: str, channel_id: str, message_limit: int) -> list[TextContent]:
    """Gemini 질문 처리"""
    slack = get_slack_service()
    gemini = get_gemini_service()

    # Slack 메시지 가져오기
    messages = slack.get_channel_messages(channel_id, limit=message_limit)

    if not messages:
        return [TextContent(type="text", text="채널에 메시지가 없어 답변할 수 없습니다.")]

    # 메시지를 컨텍스트로 변환
    context = slack.format_messages_for_context(messages)

    # Gemini에게 질문
    answer = gemini.ask_with_context(question, context)

    result = f"## Gemini 답변\n\n"
    result += f"**질문**: {question}\n\n"
    result += f"**답변**:\n{answer}\n\n"
    result += f"---\n*{len(messages)}개의 Slack 메시지를 참고했습니다.*"

    return [TextContent(type="text", text=result)]


async def handle_summarize_channel(channel_id: str, message_limit: int) -> list[TextContent]:
    """채널 요약 처리"""
    slack = get_slack_service()
    gemini = get_gemini_service()

    # Slack 메시지 가져오기
    messages = slack.get_channel_messages(channel_id, limit=message_limit)

    if not messages:
        return [TextContent(type="text", text="채널에 메시지가 없어 요약할 수 없습니다.")]

    # 메시지를 컨텍스트로 변환
    context = slack.format_messages_for_context(messages)

    # Gemini로 요약
    summary = gemini.summarize(context)

    result = f"## 채널 요약\n\n"
    result += f"{summary}\n\n"
    result += f"---\n*{len(messages)}개의 메시지를 분석했습니다.*"

    return [TextContent(type="text", text=result)]


# SSE Transport 설정
sse = SseServerTransport("/mcp/messages/")


async def handle_sse(request):
    """SSE 연결 핸들러"""
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


async def handle_health(request):
    """헬스체크 엔드포인트"""
    return JSONResponse({
        "status": "ok",
        "server": "slack-gemini-mcp",
        "version": "1.0.0"
    })


async def handle_root(request):
    """루트 엔드포인트"""
    return JSONResponse({
        "message": "Slack Gemini MCP Server",
        "endpoints": {
            "health": "/health",
            "mcp_sse": "/mcp/sse",
            "mcp_messages": "/mcp/messages/"
        },
        "usage": "Claude Desktop에서 이 URL을 MCP 서버로 등록하세요"
    })


# Starlette 앱 생성
app = Starlette(
    debug=False,
    routes=[
        Route("/", handle_root),
        Route("/health", handle_health),
        Route("/mcp/sse", handle_sse),
        Route("/mcp/messages/", sse.handle_post_message, methods=["POST"]),
    ]
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Slack Gemini MCP 서버 시작 (포트: {port})...")
    uvicorn.run(app, host="0.0.0.0", port=port)
