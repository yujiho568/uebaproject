# app/routers/credentials.py
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, Field, constr
from app.models.user import User
from app.api.v1.endpoints.user import get_current_user  # 인증 의존성
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime

from app.db.database import get_db
from app.models.aws_credential import AwsCredential
from app.schemas.aws_credential import (
    AwsCredentialCreate,
    AwsCredentialUpdate,
    AwsCredentialOut,
)
from app.crud import aws_credential as crud


router = APIRouter(prefix="/credentials/{user_id}", tags=["credentials"])

# ---------- Schemas ----------
class AwsCredsIn(BaseModel):
    # camelCase 입력도 허용하기 위해 alias 지정
    access_key_id: constr(strip_whitespace=True, min_length=8, max_length=64) = Field(..., alias="accessKeyId")
    secret_access_key: constr(strip_whitespace=True, min_length=8) = Field(..., alias="secretAccessKey")
    region: Optional[constr(strip_whitespace=True, max_length=32)] = "ap-northeast-2"

    class Config:
        # 요청은 camelCase로 받아도 되고, 서버 내에서는 snake_case로 접근 가능
        allow_population_by_field_name = False


class CheckResultOut(BaseModel):
    account: str
    arn: str
    userId: str
    region: str
    
class AwsCredentialStoreIn(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    region: constr(strip_whitespace=True, max_length=32) = "ap-northeast-2"
    access_key_id: constr(strip_whitespace=True, min_length=8, max_length=64)
    secret_access_key: constr(strip_whitespace=True, min_length=8)

class CredListOut(BaseModel):
    name: str
    region: Optional[str] = None
    created_at: datetime
    access_key_id_last4: Optional[str] = None
    has_secret: bool = False

    class Config:
        from_attributes = True
        
class AwsCredentialOut(BaseModel):
    id: int
    user_id: int
    name: str
    region: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None
    access_key_id_last4: Optional[str] = Field(None, description="Access Key ID 마지막 4자리")
    has_secret: bool = Field(False, description="secret_access_key 존재 여부")

    class Config:
        from_attributes = True  # SQLAlchemy ORM 직렬화 허용


def _mask_last4(v: Optional[str]) -> Optional[str]:
    if not v:
        return None
    return v[-4:].rjust(len(v), "*")
# ---------- Helpers ----------
def _sts_client(creds: AwsCredsIn):
    cfg = Config(
        region_name=creds.region or "ap-northeast-2",
        read_timeout=10,
        connect_timeout=5,
        retries={"max_attempts": 3, "mode": "standard"},
    )
    return boto3.client(
        "sts",
        aws_access_key_id=creds.access_key_id,
        aws_secret_access_key=creds.secret_access_key,
        # session_token을 사용하지 않는 IAM 고정 키 시나리오이므로 생략
        config=cfg,
    )
# ---------- API Endpoints ----------
@router.post("/check", response_model=CheckResultOut, summary="Check IAM credentials by STS GetCallerIdentity")
def check_credentials(
    payload: AwsCredsIn,
    user_id: int = Path(..., ge=1),
):
    """
    전달받은 Access Key / Secret Access Key로 STS `GetCallerIdentity`를 호출해
    **유효한 자격증명인지** 확인합니다.
    - 성공: account / arn / userId 반환
    - 실패: 401/403/400 에러
    """
    sts = _sts_client(payload)
    try:
        res = sts.get_caller_identity()
        return CheckResultOut(
            account=res.get("Account"),
            arn=res.get("Arn"),
            userId=res.get("UserId"),
            region=payload.region or "ap-northeast-2",
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "UnknownError")
        msg = e.response.get("Error", {}).get("Message", "Authentication failed")
        # 에러 코드에 따라 상태코드 매핑
        if code in ("InvalidClientTokenId", "SignatureDoesNotMatch", "UnrecognizedClientException"):
            # 보통 키 자체가 틀렸거나 서명 오류
            raise HTTPException(status_code=401, detail=f"{code}: {msg}")
        elif code in ("AccessDenied", "AccessDeniedException"):
            # 자격증명은 유효하나 STS가 막힌 정책 등
            raise HTTPException(status_code=403, detail=f"{code}: {msg}")
        else:
            raise HTTPException(status_code=400, detail=f"{code}: {msg}")
    except Exception as e:
        # 네트워크 문제 등 일반 예외
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/store", response_model=AwsCredentialOut, status_code=201)
def store_credential(
    payload: AwsCredentialStoreIn,
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    자격증명을 DB에 저장합니다.
    - 프론트에서 이미 check로 유효성 테스트 후 저장 호출을 가정
    - 동일 user_id 내 name은 유니크 제약
    - secret_access_key는 로컬 개발용으로 평문 저장 (운영 환경에서는 암호화 필요)
    """
    cred = AwsCredential(
        user_id=user_id,
        name=payload.name,
        region=payload.region,
        access_key_id=payload.access_key_id,
        secret_access_key=payload.secret_access_key,
    )

    db.add(cred)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Credential name already exists")
    db.refresh(cred)

    return AwsCredentialOut(
        id=cred.id,
        user_id=cred.user_id,
        name=cred.name,
        region=cred.region,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
        last_used_at=cred.last_used_at,
        access_key_id_last4=_mask_last4(cred.access_key_id),
        has_secret=bool(cred.secret_access_key),
    )
    
@router.get("/list", response_model=List[CredListOut])
def list_credentials(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    creds = (
        db.query(AwsCredential)
        .filter(AwsCredential.user_id == user_id)
        .order_by(AwsCredential.created_at.desc())
        .all()
    )
    out = []
    for c in creds:
        out.append(CredListOut(
            name=c.name,
            region=c.region,
            created_at=c.created_at,
            access_key_id_last4=_mask_last4(c.access_key_id),
            has_secret=bool(c.secret_access_key),
        ))
    return out

@router.delete("/{name}")
def delete_credential(
    user_id: int = Path(..., ge=1),
    name: str = Path(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    cred = db.query(AwsCredential).filter(
        AwsCredential.user_id == user_id,
        AwsCredential.name == name
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    db.delete(cred)
    db.commit()
    return {"ok": True, "deleted": name}