from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # AWS 관련 필드 추가
    aws_access_key = Column(String, nullable=True)
    aws_secret_key = Column(String, nullable=True)  # 운영환경에서는 암호화 저장 강력 권장!
    aws_account_id = Column(String, nullable=True)  # STS get_caller_identity()로 확인한 AWS 계정 ID
    aws_principal_arn = Column(String, nullable=True)  # ex) arn:aws:iam::<account-id>:root

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
