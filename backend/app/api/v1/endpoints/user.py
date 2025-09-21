# app/api/v1/users.py  (예: 너가 보여준 라우터 파일)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.schemas.user import UserCreate, UserRead, Token, UserLogin
from app.crud.user import create_user, get_user_by_email
from app.core.security import verify_password, create_access_token, decode_access_token
from app.models.user import User
from app.db.database import get_db

# boto3 추가
import boto3
from botocore.exceptions import NoCredentialsError, ClientError, EndpointConnectionError, BotoCoreError

router = APIRouter(prefix="/users", tags=["users"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


def _is_root_credentials(aws_access_key: str, aws_secret_key: str) -> tuple[bool, str, str]:
    """
    제공된 자격 증명이 루트 계정인지 확인한다.
    - STS GetCallerIdentity 호출
    - ARN이 'arn:aws:iam::<account-id>:root' 형식이면 루트로 판단
    반환: (is_root, account_id, arn)
    예외는 상위에서 처리
    """
    # STS는 글로벌 서비스이지만, 지역 지정이 필요할 수 있어 기본 us-east-1 사용
    session = boto3.Session(
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name="us-east-1",
    )
    sts = session.client("sts")
    resp = sts.get_caller_identity()  # 권한 없이 누구나 호출 가능(명시적 Deny 제외)
    arn = resp.get("Arn", "")
    account_id = resp.get("Account", "")
    is_root = arn.endswith(":root")
    return is_root, account_id, arn


@router.post("/register", response_model=UserRead)
def register(user: UserCreate, db: Session = Depends(get_db)):
    print("DEBUG user model:", user)
    # Pydantic v2
    try:
        print("DEBUG dump:", user.model_dump())
    except Exception:
        # v1 호환
        print("DEBUG dump:", user.dict())
    ...

    email = (user.email or "").strip().lower()
    db_user = get_user_by_email(db, email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # AWS 크리덴셜 존재 검증
    if not getattr(user, "aws_access_key", None) or not getattr(user, "aws_secret_key", None):
        raise HTTPException(status_code=400, detail="AWS credentials required")

    # 루트 계정 여부 확인
    try:
        is_root, account_id, arn = _is_root_credentials(user.aws_access_key, user.aws_secret_key)
    except (NoCredentialsError, EndpointConnectionError) as e:
        # 네트워크/환경 문제 또는 형식 오류
        raise HTTPException(status_code=400, detail="Invalid AWS credentials or network error") from e
    except ClientError as e:
        # 명시적 Deny 등으로 sts 호출 실패
        # 민감 정보 노출 방지를 위해 상세 사유는 숨김
        raise HTTPException(status_code=400, detail="Failed to validate AWS credentials with STS") from e
    except BotoCoreError as e:
        raise HTTPException(status_code=400, detail="AWS validation error") from e

    if not is_root:
        # 루트가 아니면 가입 거부 (요구사항에 따라 조정 가능)
        raise HTTPException(
            status_code=400,
            detail="Provided AWS credentials are not for the ROOT account"
        )

    # 여기까지 왔다면 루트 확인 완료
    user.email = email
    # 필요하다면 account_id/arn을 DB에 보존하도록 스키마/모델에 필드 추가 가능
    # 예: user.aws_account_id = account_id  / user.aws_principal_arn = arn

    return create_user(db, user)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = (form_data.username or "").strip().lower()
    user = get_user_by_email(db, email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub") if payload else None
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user


@router.get("/me", response_model=UserRead)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
