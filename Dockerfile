# Dockerfile
# UEBA System - 모듈화된 FastAPI 구조용 Docker 이미지

FROM python:3.11-slim

# 메타데이터
LABEL maintainer="UEBA System Team"
LABEL description="UEBA System - 모듈화된 FastAPI 백엔드"
LABEL version="1.0.0"

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐싱 최적화를 위해 먼저 복사)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사 (모듈화된 구조)
COPY main.py .
COPY app/ ./app/
COPY core/ ./core/
COPY db/ ./db/
COPY models/ ./models/
COPY schemas/ ./schemas/
COPY crud/ ./crud/
COPY api/ ./api/
COPY tests/ ./tests/

# 필요한 디렉토리 생성
RUN mkdir -p /app/data /app/logs /app/profiles

# Python 패키지 경로 설정
ENV PYTHONPATH=/app

# 환경변수 기본값 설정
ENV DATABASE_URL=sqlite:///./data/ueba_system.db
ENV DEBUG=false
ENV LOG_LEVEL=INFO

# 포트 노출
EXPOSE 8000

# 헬스체크 설정 (모듈화된 API 구조 반영)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 비root 사용자 생성 및 권한 설정 (보안)
RUN groupadd -r ueba && useradd -r -g ueba ueba
RUN chown -R ueba:ueba /app
USER ueba

# 애플리케이션 실행
CMD ["python", "-m", "uv# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for database and logs
RUN mkdir -p /app/data /app/logs

# Expose port
EXPOSE 8000

# Environment variables
ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite:///./data/ueba_system.db

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]