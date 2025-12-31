# Slack Gemini MCP Server

Slack 메시지를 기반으로 Google Gemini가 답변하는 MCP 서버입니다.
Claude Desktop/Code에서 Slack 채널의 대화 내용을 검색하고, 이를 기반으로 질문에 답변받을 수 있습니다.

## 기능

| 도구 | 설명 |
|------|------|
| `list_slack_channels` | Slack 워크스페이스의 채널 목록 조회 |
| `get_slack_messages` | 특정 채널의 최근 메시지 조회 |
| `search_slack_messages` | 키워드로 메시지 검색 |
| `ask_gemini_about_slack` | Slack 메시지를 컨텍스트로 Gemini에게 질문 |
| `summarize_slack_channel` | 채널 대화 요약 |

---

## 방법 1: 원격 MCP 서버 (Cloud Run) - 권장

다른 유저들이 쉽게 사용할 수 있도록 Cloud Run에 배포된 서버를 사용합니다.

### 클라이언트 설정 (사용자)

배포된 서버 URL을 Claude Desktop 설정에 추가합니다.

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "slack-gemini": {
      "url": "https://slack-gemini-mcp-xxxxx-du.a.run.app/mcp/sse"
    }
  }
}
```

> 배포 후 실제 Cloud Run URL로 교체하세요.

### 서버 배포 (관리자)

#### 1. GitHub Repository 생성 및 Secrets 설정

GitHub Repository → Settings → Secrets and variables → Actions

| Secret 이름 | 값 |
|------------|-----|
| `GCP_PROJECT_ID` | Google Cloud 프로젝트 ID |
| `GCP_SA_KEY` | 서비스 계정 JSON 키 전체 |
| `GCP_REGION` | `asia-northeast3` (서울) |
| `SLACK_BOT_TOKEN` | Slack Bot Token |
| `GEMINI_API_KEY` | Gemini API Key |

#### 2. 코드 푸시

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-repo/slack-gemini-mcp.git
git push -u origin main
```

GitHub Actions가 자동으로 Cloud Run에 배포합니다.

#### 3. 배포 확인

Cloud Run 콘솔에서 서비스 URL 확인:
`https://slack-gemini-mcp-xxxxx-du.a.run.app`

---

## 방법 2: 로컬 MCP 서버

각 사용자가 자신의 PC에서 직접 실행합니다.

### 1. 의존성 설치

```bash
cd slack-gemini-mcp
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 다음 값을 설정:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
GEMINI_API_KEY=your-gemini-api-key
```

### 3. Claude Desktop 설정

`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "slack-gemini": {
      "command": "python",
      "args": ["C:/path/to/slack-gemini-mcp/src/server.py"]
    }
  }
}
```

### 4. Claude Code 설정

프로젝트 루트에 `.mcp.json` 파일 생성:

```json
{
  "mcpServers": {
    "slack-gemini": {
      "command": "python",
      "args": ["./slack-gemini-mcp/src/server.py"]
    }
  }
}
```

---

## Slack App 설정

1. [Slack API](https://api.slack.com/apps)에서 앱 생성
2. **OAuth & Permissions**에서 Bot Token Scopes 추가:
   - `channels:read`
   - `channels:history`
   - `groups:read` (private 채널용)
   - `groups:history`
   - `users:read`
   - `search:read`
3. 워크스페이스에 앱 설치
4. Bot User OAuth Token 복사

## Gemini API Key 발급

1. [Google AI Studio](https://makersuite.google.com/app/apikey) 접속
2. API Key 생성 및 복사

---

## 사용 예시

Claude에서 자연어로 요청하면 됩니다:

```
"Slack 채널 목록 보여줘"
"#general 채널의 최근 메시지 50개 가져와"
"#dev 채널에서 '배포' 관련 메시지 검색해줘"
"#project 채널 대화를 기반으로 이번 주 진행 상황 알려줘"
"#meeting 채널 요약해줘"
```

---

## 프로젝트 구조

```
slack-gemini-mcp/
├── src/
│   ├── __init__.py
│   ├── server.py          # MCP 서버 (로컬용, stdio)
│   ├── server_sse.py      # MCP 서버 (원격용, SSE)
│   ├── slack_service.py   # Slack API 래퍼
│   └── gemini_service.py  # Gemini API 래퍼
├── .github/
│   └── workflows/
│       └── deploy.yml     # Cloud Run 배포 워크플로우
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 문제 해결

### "SLACK_BOT_TOKEN이 설정되지 않았습니다"
- 로컬: `.env` 파일 확인
- Cloud Run: GitHub Secrets 또는 Cloud Run 환경변수 확인

### 채널을 찾을 수 없음
- Slack 앱이 해당 채널에 추가되었는지 확인
- Private 채널은 앱을 채널에 초대해야 접근 가능

### Gemini 응답 오류
- API 키가 유효한지 확인
- 모델명이 `gemini-2.0-flash`인지 확인

### Cloud Run 연결 실패
- 서비스가 `allow-unauthenticated`로 배포되었는지 확인
- URL이 `/mcp/sse`로 끝나는지 확인
