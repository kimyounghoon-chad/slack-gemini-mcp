FROM python:3.12-slim

WORKDIR /app

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY src/ ./src/

# 작업 디렉토리를 src로 변경
WORKDIR /app/src

# 포트 설정
EXPOSE 8080

# SSE 서버 실행
CMD ["python", "server_sse.py"]
