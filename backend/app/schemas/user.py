from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

# ---- Base ----
class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True

# ---- Create (request body for /register) ----
class UserCreate(UserBase):
    password: str
    aws_access_key: str
    aws_secret_key: str

    class Config:
        from_attributes = True  # pydantic v2에서도 동작 (v1은 orm_mode와 유사)

# ---- Read (response for /users/me, /register) ----
class UserRead(UserBase):
    id: int
    created_at: datetime
    aws_access_key: Optional[str] = None
    aws_account_id: Optional[str] = None
    aws_principal_arn: Optional[str] = None
    # 보안상 aws_secret_key는 응답에 포함 X

    class Config:
        from_attributes = True

# ---- Internal (DB-facing) ----
class UserInDB(UserBase):
    id: int
    hashed_password: str
    created_at: datetime
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_account_id: Optional[str] = None
    aws_principal_arn: Optional[str] = None

    class Config:
        from_attributes = True

# ---- Auth token ----
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# ---- Login body ----
class UserLogin(BaseModel):
    email: EmailStr
    password: str
