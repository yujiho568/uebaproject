from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.schemas.user import UserCreate
from passlib.context import CryptContext
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Optional: Fernet 암호화 유틸 ---
try:
    from cryptography.fernet import Fernet
    _FERNET_KEY = os.getenv("FERNET_KEY")  # 예: base64 urlsafe key
    _fernet = Fernet(_FERNET_KEY) if _FERNET_KEY else None
except Exception:
    _fernet = None

def _encrypt_secret(value: str | None) -> str | None:
    if not value:
        return value
    if _fernet:
        return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    # 운영에서는 반드시 키를 설정하세요!
    return value  # 폴백(평문)

def get_user_by_email(db: Session, email: str):
    normalized = (email or "").strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized).first()

def create_user(db: Session, user: UserCreate):
    """
    UserCreate에 포함된 필드:
      - email, password (필수)
      - aws_access_key, aws_secret_key (필수로 받는 경우)
      - (옵션) aws_account_id, aws_principal_arn  # register에서 STS 검증 후 세팅 가능
    """
    normalized_email = (user.email or "").strip().lower()
    hashed_password = pwd_context.hash(user.password)

    db_user = User(
        email=normalized_email,
        hashed_password=hashed_password,
        aws_access_key=getattr(user, "aws_access_key", None),
        aws_secret_key=_encrypt_secret(getattr(user, "aws_secret_key", None)),
        aws_account_id=getattr(user, "aws_account_id", None),
        aws_principal_arn=getattr(user, "aws_principal_arn", None),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()
