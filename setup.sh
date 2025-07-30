#!/bin/bash
# setup.sh
# UEBA System Docker 환경 설정 스크립트 (모듈화된 구조 버전)

set -e

echo "🚀 UEBA System Docker 환경 설정을 시작합니다... (모듈화된 구조)"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로그 함수들
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Docker 및 Docker Compose 설치 확인
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되지 않았습니다. Docker를 먼저 설치해주세요."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되지 않았습니다. Docker Compose를 먼저 설치해주세요."
        exit 1
    fi
    
    log_success "Docker 및 Docker Compose 확인 완료"
}

# 프로젝트 구조 검증
check_project_structure() {
    log_info "프로젝트 구조를 검증합니다..."
    
    required_files=(
        "app/main.py"
        "requirements.txt"
        "docker-compose.yml"
        "app/core/config.py"
        "app/core/security.py"
        "app/db/database.py"
        "app/models/user.py"
        "app/schemas/user.py"
        "app/crud/user.py"
        "app/api/v1/routers.py"
        "app/api/v1/endpoints/user.py"
    )
    
    missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        log_error "다음 필수 파일들이 누락되었습니다:"
        for file in "${missing_files[@]}"; do
            echo "  - $file"
        done
        log_error "모든 파일을 올바른 위치에 생성한 후 다시 실행해주세요."
        exit 1
    fi
    
    log_success "프로젝트 구조 검증 완료"
}

# 필요한 디렉토리 생성
create_directories() {
    log_info "필요한 디렉토리를 생성합니다..."
    
    # 데이터 디렉토리들
    mkdir -p data
    mkdir -p logs
    mkdir -p profiles
    mkdir -p nginx/logs
    mkdir -p nginx/ssl
    
    # Python 패키지를 위한 __init__.py 파일들 생성
    touch app/__init__.py 2>/dev/null || mkdir -p app && touch app/__init__.py
    touch app/core/__init__.py 2>/dev/null || mkdir -p app/core && touch app/core/__init__.py
    touch app/db/__init__.py 2>/dev/null || mkdir -p app/db && touch app/db/__init__.py
    touch app/models/__init__.py 2>/dev/null || mkdir -p app/models && touch app/models/__init__.py
    touch app/schemas/__init__.py 2>/dev/null || mkdir -p app/schemas && touch app/schemas/__init__.py
    touch app/crud/__init__.py 2>/dev/null || mkdir -p app/crud && touch app/crud/__init__.py
    touch app/api/__init__.py 2>/dev/null || mkdir -p app/api && touch app/api/__init__.py
    touch app/api/v1/__init__.py 2>/dev/null || mkdir -p app/api/v1 && touch app/api/v1/__init__.py
    touch app/api/v1/endpoints/__init__.py 2>/dev/null || mkdir -p app/api/v1/endpoints && touch app/api/v1/endpoints/__init__.py
    touch app/tests/__init__.py 2>/dev/null || mkdir -p app/tests && touch app/tests/__init__.py
    
    log_success "디렉토리 및 Python 패키지 구조 생성 완료"
}

# 환경 변수 파일 생성
create_env_file() {
    if [ ! -f .env ]; then
        log_info ".env 파일을 생성합니다..."
        
        # 보안을 위한 랜덤 시크릿 키 생성
        SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "your-super-secret-key-change-this-in-production-at-least-32-chars")
        
        cat > .env << EOF
# UEBA System Environment Configuration (모듈화된 구조)

# Security
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=postgresql://ueba_user:ueba_password@postgres:5432/ueba_system

# Redis
REDIS_URL=redis://redis:6379/0

# AWS Configuration (필요시 설정)
AWS_REGION=ap-northeast-2
# AWS_ACCESS_KEY_ID=your-aws-access-key
# AWS_SECRET_ACCESS_KEY=your-aws-secret-key

# Application
APP_NAME=UEBA System
APP_VERSION=1.0.0
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# UEBA Settings
AUTO_BLOCK_THRESHOLD=0.75
DEFAULT_ANOMALY_THRESHOLD=0.7
MIN_PROFILE_SAMPLES=200

# File Storage
DATA_DIRECTORY=./data
PROFILE_DIRECTORY=./data/profiles
EVENT_DIRECTORY=./data/events

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF
        
        log_success ".env 파일 생성 완료"
    else
        log_info ".env 파일이 이미 존재합니다."
    fi
}

# Nginx 설정 파일 생성
create_nginx_config() {
    if [ ! -f nginx/nginx.conf ]; then
        log_info "Nginx 설정 파일을 생성합니다..."
        
        mkdir -p nginx
        
        cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream ueba_backend {
        server ueba-api:8000;
    }
    
    server {
        listen 80;
        server_name localhost;
        
        # API 라우팅
        location /api/ {
            proxy_pass http://ueba_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # 루트 및 헬스체크
        location / {
            proxy_pass http://ueba_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /health {
            proxy_pass http://ueba_backend/health;
            access_log off;
        }
        
        location /docs {
            proxy_pass http://ueba_backend/docs;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF
        
        log_success "Nginx 설정 파일 생성 완료"
    else
        log_info "Nginx 설정 파일이 이미 존재합니다."
    fi
}

# Python 가상환경 의존성 확인 (선택사항)
check_python_dependencies() {
    if command -v python3 &> /dev/null; then
        log_info "Python 의존성을 확인합니다..."
        
        # requirements.txt 파일 내용 검증
        if [ -f requirements.txt ]; then
            required_packages=("fastapi" "uvicorn" "sqlalchemy" "psycopg2-binary" "python-jose" "passlib")
            missing_packages=()
            
            for package in "${required_packages[@]}"; do
                if ! grep -q "^${package}" requirements.txt; then
                    missing_packages+=("$package")
                fi
            done
            
            if [ ${#missing_packages[@]} -ne 0 ]; then
                log_warning "requirements.txt에서 다음 패키지가 누락되었을 수 있습니다:"
                for package in "${missing_packages[@]}"; do
                    echo "  - $package"
                done
            else
                log_success "requirements.txt 검증 완료"
            fi
        else
            log_warning "requirements.txt 파일을 찾을 수 없습니다."
        fi
    fi
}

# Docker 이미지 빌드
build_images() {
    log_info "Docker 이미지를 빌드합니다..."
    
    # 빌드 전 컨테이너 정리
    docker-compose down 2>/dev/null || true
    
    # 캐시 없이 빌드
    docker-compose build --no-cache
    
    if [ $? -eq 0 ]; then
        log_success "Docker 이미지 빌드 완료"
    else
        log_error "Docker 이미지 빌드 실패"
        exit 1
    fi
}

# 컨테이너 시작
start_containers() {
    log_info "컨테이너를 시작합니다..."
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        log_success "컨테이너 시작 완료"
    else
        log_error "컨테이너 시작 실패"
        exit 1
    fi
}

# 개발용 컨테이너 시작 (pgAdmin, Redis Commander 포함)
start_dev_containers() {
    log_info "개발용 컨테이너를 시작합니다..."
    docker-compose --profile dev up -d
    
    if [ $? -eq 0 ]; then
        log_success "개발용 컨테이너 시작 완료"
    else
        log_error "개발용 컨테이너 시작 실패"
        exit 1
    fi
}

# 컨테이너 상태 확인
check_containers() {
    log_info "컨테이너 상태를 확인합니다..."
    sleep 15  # 모듈화된 구조는 초기화 시간이 더 필요할 수 있음
    
    # PostgreSQL 상태 확인
    if docker-compose exec -T postgres pg_isready -U ueba_user -d ueba_system > /dev/null 2>&1; then
        log_success "PostgreSQL 연결 확인"
    else
        log_warning "PostgreSQL 연결 실패 (시작 중일 수 있습니다)"
    fi
    
    # Redis 상태 확인
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        log_success "Redis 연결 확인"
    else
        log_warning "Redis 연결 실패"
    fi
    
    # API 서버 상태 확인 (모듈화된 구조)
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "API 서버 연결 확인"
            break
        else
            attempt=$((attempt + 1))
            if [ $attempt -eq $max_attempts ]; then
                log_warning "API 서버 연결 실패 (더 많은 시간이 필요할 수 있습니다)"
            else
                sleep 2
            fi
        fi
    done
    
    # 모듈화된 API 엔드포인트 확인
    if curl -f http://localhost:8000/api/v1/system/guide > /dev/null 2>&1; then
        log_success "모듈화된 API 엔드포인트 확인"
    else
        log_warning "모듈화된 API 엔드포인트 확인 실패"
    fi
}

# 기본 계정 정보 및 엔드포인트 출력
show_system_info() {
    log_info "시스템 정보:"
    echo "=========================================="
    echo "🔐 기본 계정 정보:"
    echo "  관리자: admin / admin123"
    echo ""
    echo "🌐 웹 인터페이스:"
    echo "  API 서버: http://localhost:8000"
    echo "  API 문서: http://localhost:8000/docs"
    echo "  헬스체크: http://localhost:8000/health"
    echo "  시스템 가이드: http://localhost:8000/api/v1/system/guide"
    echo ""
    echo "🛠️ 관리 도구:"
    echo "  pgAdmin: http://localhost:5050 (admin@ueba.com / admin123)"
    echo "  Redis Commander: http://localhost:8081"
    echo ""
    echo "📡 주요 API 엔드포인트:"
    echo "  POST /api/v1/auth/register - 회원가입"
    echo "  POST /api/v1/auth/login - 로그인"
    echo "  GET  /api/v1/auth/me - 사용자 정보"
    echo "  GET  /api/v1/system/status - 시스템 상태"
    echo "  GET  /api/v1/system/users - 사용자 목록 (관리자)"
    echo ""
    echo "🧪 테스트:"
    echo "  python test_api.py - API 테스트"
    echo "=========================================="
}

# 메인 설정 함수
main() {
    echo "======================================"
    echo "  UEBA System Docker Setup v2.0"
    echo "  (모듈화된 FastAPI 구조)"
    echo "======================================"
    
    # 옵션 파싱
    ENVIRONMENT="production"
    SKIP_BUILD=false
    SKIP_CHECK=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                ENVIRONMENT="development"
                shift
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-check)
                SKIP_CHECK=true
                shift
                ;;
            -h|--help)
                echo "사용법: $0 [옵션]"
                echo "옵션:"
                echo "  --dev         개발 환경으로 설정 (pgAdmin, Redis Commander 포함)"
                echo "  --skip-build  이미지 빌드 건너뛰기"
                echo "  --skip-check  프로젝트 구조 검증 건너뛰기"
                echo "  -h, --help    도움말 출력"
                exit 0
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                exit 1
                ;;
        esac
    done
    
    check_docker
    
    if [ "$SKIP_CHECK" = false ]; then
        check_project_structure
    fi
    
    create_directories
    create_env_file
    create_nginx_config
    check_python_dependencies
    
    if [ "$SKIP_BUILD" = false ]; then
        build_images
    fi
    
    if [ "$ENVIRONMENT" = "development" ]; then
        start_dev_containers
    else
        start_containers
    fi
    
    check_containers
    show_system_info
    
    log_success "UEBA System Docker 환경 설정이 완료되었습니다!"
    
    if [ "$ENVIRONMENT" = "development" ]; then
        log_info "개발 모드로 실행 중입니다. 모든 개발 도구에 접근할 수 있습니다."
    fi
    
    echo ""
    log_info "유용한 명령어들:"
    echo "  docker-compose logs -f ueba-api    # API 로그 확인"
    echo "  docker-compose logs -f postgres    # DB 로그 확인"
    echo "  docker-compose ps                  # 컨테이너 상태"
    echo "  docker-compose restart ueba-api    # API 서버 재시작"
    echo "  docker-compose down                # 컨테이너 중지"
    echo "  docker-compose down -v             # 데이터 포함 완전 삭제"
    echo "  python test_api.py                 # API 테스트"
}

# 신호 처리 (Ctrl+C)
trap 'echo -e "\n${YELLOW}설정이 중단되었습니다.${NC}"; exit 1' INT

# 스크립트 실행
main "$@"