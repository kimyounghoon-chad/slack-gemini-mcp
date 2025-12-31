"""
Slack 서비스 모듈
Slack API를 사용하여 채널 및 메시지 조회
"""

import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()
logger = logging.getLogger(__name__)


class SlackService:
    """Slack API 서비스 클래스"""

    def __init__(self, token: Optional[str] = None):
        """
        SlackService 초기화

        Args:
            token: Slack Bot Token (없으면 환경변수에서 로드)
        """
        self.token = token or os.getenv('SLACK_BOT_TOKEN')

        if not self.token:
            raise ValueError(
                "SLACK_BOT_TOKEN이 설정되지 않았습니다. "
                ".env 파일 또는 환경변수를 확인하세요."
            )

        self.client = WebClient(token=self.token)
        self._user_cache: dict = {}

    def get_channels(self, types: str = "public_channel,private_channel") -> list:
        """
        워크스페이스의 채널 목록 조회

        Args:
            types: 조회할 채널 유형

        Returns:
            채널 정보 리스트
        """
        channels = []
        cursor = None

        try:
            while True:
                response = self.client.conversations_list(
                    types=types,
                    limit=200,
                    cursor=cursor
                )

                channels.extend(response['channels'])
                cursor = response.get('response_metadata', {}).get('next_cursor')

                if not cursor:
                    break

            logger.info(f"총 {len(channels)}개의 채널을 조회했습니다.")
            return channels

        except SlackApiError as e:
            logger.error(f"채널 목록 조회 실패: {e.response['error']}")
            raise

    def get_channel_messages(
        self,
        channel_id: str,
        limit: int = 100
    ) -> list:
        """
        채널의 메시지 히스토리 조회

        Args:
            channel_id: 채널 ID
            limit: 조회할 최대 메시지 수

        Returns:
            메시지 리스트
        """
        messages = []
        cursor = None
        remaining = limit

        try:
            while remaining > 0:
                fetch_count = min(remaining, 200)
                response = self.client.conversations_history(
                    channel=channel_id,
                    limit=fetch_count,
                    cursor=cursor
                )

                batch = response.get('messages', [])
                messages.extend(batch)
                remaining -= len(batch)

                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor or not batch:
                    break

            logger.info(f"채널 {channel_id}에서 {len(messages)}개의 메시지를 조회했습니다.")
            return messages

        except SlackApiError as e:
            logger.error(f"메시지 조회 실패 ({channel_id}): {e.response['error']}")
            return []

    def get_user_name(self, user_id: str) -> str:
        """
        사용자 ID로 이름 조회 (캐시 사용)

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 이름 또는 ID
        """
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            response = self.client.users_info(user=user_id)
            user = response['user']
            name = user.get('real_name') or user.get('name') or user_id
            self._user_cache[user_id] = name
            return name
        except SlackApiError:
            return user_id

    def search_messages(self, query: str) -> list:
        """
        메시지 검색 (Slack 검색 API 사용)

        Args:
            query: 검색 키워드

        Returns:
            검색된 메시지 리스트
        """
        try:
            response = self.client.search_messages(query=query)
            matches = response.get('messages', {}).get('matches', [])
            logger.info(f"'{query}' 검색 결과: {len(matches)}개")
            return matches
        except SlackApiError as e:
            logger.error(f"메시지 검색 실패: {e.response['error']}")
            return []

    def format_messages_for_context(self, messages: list) -> str:
        """
        메시지 리스트를 LLM 컨텍스트용 텍스트로 변환

        Args:
            messages: Slack 메시지 리스트

        Returns:
            포맷된 텍스트
        """
        formatted = []

        # 시간순 정렬 (오래된 것부터)
        sorted_messages = sorted(
            messages,
            key=lambda m: float(m.get('ts', 0))
        )

        for msg in sorted_messages:
            user_id = msg.get('user', 'unknown')
            user_name = self.get_user_name(user_id)
            text = msg.get('text', '')
            ts = msg.get('ts', '')

            # 타임스탬프 변환
            try:
                dt = datetime.fromtimestamp(float(ts))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                time_str = ""

            formatted.append(f"[{time_str}] {user_name}: {text}")

        return "\n".join(formatted)

    def get_channel_info(self, channel_id: str) -> dict:
        """
        채널 정보 조회

        Args:
            channel_id: 채널 ID

        Returns:
            채널 정보 딕셔너리
        """
        try:
            response = self.client.conversations_info(channel=channel_id)
            return response['channel']
        except SlackApiError as e:
            logger.error(f"채널 정보 조회 실패 ({channel_id}): {e.response['error']}")
            return {}
