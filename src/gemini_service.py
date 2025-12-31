"""
Gemini 서비스 모듈
Google Gemini API를 사용하여 Slack 메시지 기반 질문 답변 및 요약
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
logger = logging.getLogger(__name__)


class GeminiService:
    """Google Gemini API 서비스 클래스"""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        """
        GeminiService 초기화

        Args:
            api_key: Gemini API 키 (없으면 환경변수에서 로드)
            model_name: 사용할 Gemini 모델 이름
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY가 설정되지 않았습니다. "
                ".env 파일 또는 환경변수를 확인하세요."
            )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        logger.info(f"Gemini 서비스 초기화 완료 (모델: {model_name})")

    def ask_with_context(self, question: str, context: str) -> str:
        """
        컨텍스트(Slack 메시지)를 기반으로 질문에 답변

        Args:
            question: 사용자 질문
            context: Slack 메시지 컨텍스트

        Returns:
            Gemini의 답변
        """
        prompt = f"""다음은 Slack 채널의 대화 내용입니다. 이 대화 내용을 참고하여 질문에 답변해주세요.

## Slack 대화 내용
{context}

## 질문
{question}

## 답변 지침
1. 위의 Slack 대화 내용을 기반으로 답변해주세요.
2. 대화 내용에서 관련 정보를 찾을 수 없다면 그렇게 말씀해주세요.
3. 답변은 명확하고 간결하게 작성해주세요.
4. 필요한 경우 대화에서 인용한 내용을 언급해주세요.
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini 질문 처리 실패: {e}")
            raise

    def summarize(self, context: str) -> str:
        """
        Slack 대화 내용 요약

        Args:
            context: Slack 메시지 컨텍스트

        Returns:
            요약된 내용
        """
        prompt = f"""다음 Slack 대화 내용을 요약해주세요.

## Slack 대화 내용
{context}

## 요약 지침
1. 주요 논의 주제를 파악해주세요.
2. 중요한 결정사항이나 액션 아이템이 있다면 포함해주세요.
3. 참여자들의 주요 의견을 정리해주세요.
4. 요약은 한국어로 작성해주세요.
5. 글머리 기호를 사용하여 구조적으로 정리해주세요.
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini 요약 처리 실패: {e}")
            raise

    def analyze_sentiment(self, context: str) -> str:
        """
        대화의 전반적인 분위기/감정 분석

        Args:
            context: Slack 메시지 컨텍스트

        Returns:
            분위기 분석 결과
        """
        prompt = f"""다음 Slack 대화의 전반적인 분위기와 감정을 분석해주세요.

## Slack 대화 내용
{context}

## 분석 지침
1. 대화의 전반적인 톤(긍정적/부정적/중립적)을 파악해주세요.
2. 참여자들의 감정 상태를 추측해주세요.
3. 특별히 주목할만한 감정적 변화가 있다면 언급해주세요.
4. 팀 분위기나 협업 상태에 대한 인사이트를 제공해주세요.
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini 감정 분석 실패: {e}")
            raise

    def extract_action_items(self, context: str) -> str:
        """
        대화에서 액션 아이템 추출

        Args:
            context: Slack 메시지 컨텍스트

        Returns:
            추출된 액션 아이템
        """
        prompt = f"""다음 Slack 대화에서 액션 아이템(할 일, 작업 항목)을 추출해주세요.

## Slack 대화 내용
{context}

## 추출 지침
1. 명시적으로 언급된 작업 항목을 찾아주세요.
2. 암묵적으로 합의된 작업도 포함해주세요.
3. 가능하다면 담당자와 기한을 함께 표시해주세요.
4. 우선순위가 언급되었다면 표시해주세요.

## 출력 형식
- [ ] 액션 아이템 1 (담당: OOO, 기한: OOO)
- [ ] 액션 아이템 2 ...
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini 액션 아이템 추출 실패: {e}")
            raise

    def is_ready(self) -> bool:
        """서비스 준비 상태 확인"""
        return self.api_key is not None and self.model is not None
