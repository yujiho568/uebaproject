# app/api/v1/endpoints/results.py
from fastapi import APIRouter, Path, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.results import ImportS3Request, ImportS3Summary
from app.services.s3_import import get_stored_credentials, import_s3_jsons

# 추가 import
from app.models.user import User
import os
try:
    from cryptography.fernet import Fernet
    _FERNET = Fernet(os.getenv("FERNET_KEY")) if os.getenv("FERNET_KEY") else None
except Exception:
    _FERNET = None

def _decrypt_secret(v: str | None) -> str | None:
    if not v:
        return v
    if _FERNET:
        try:
            return _FERNET.decrypt(v.encode()).decode()
        except Exception:
            # 암호화 안된 값이면 그대로 사용 (개발 환경 폴백)
            return v
    return v

router = APIRouter(prefix="/results/{user_id}", tags=["results"])

@router.post("/import-s3", response_model=ImportS3Summary)
def import_from_s3(
    payload: ImportS3Request,
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    저장된 Credential(name) 또는 회원가입 때 저장한 User 루트 키로 S3 JSON을 적재.
    - credential_name == "__USER_ROOT__" 이면 User 테이블의 aws_access_key / aws_secret_key 사용
    - dry_run=True 이면 DB에는 쓰지 않음
    """
    use_user_root = payload.credential_name == "__USER_ROOT__"

    if use_user_root:
        print(f"[DEBUG] Using user {user_id}'s stored root credentials")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        if not user.aws_access_key or not user.aws_secret_key:
            raise HTTPException(status_code=400, detail="User has no stored AWS credentials")
        access_key_id = user.aws_access_key
        secret_access_key = _decrypt_secret(user.aws_secret_key)
        region = payload.region or "ap-northeast-2"
        credential_tag = "user_root"
    else:
        print(f"[DEBUG] Using stored credential: {payload.credential_name}")
        try:
            cred = get_stored_credentials(db, user_id, payload.credential_name)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        access_key_id = cred.access_key_id
        secret_access_key = cred.secret_access_key
        region = payload.region or (cred.region or "ap-northeast-2")
        credential_tag = payload.credential_name

    scanned, imported, skipped, errors, first_key, last_key = import_s3_jsons(
        db=db,
        user_id=user_id,
        bucket=payload.bucket,
        prefix=payload.prefix,
        region=region,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        max_files=payload.max_files,
        dry_run=payload.dry_run,
        credential_name=credential_tag,  # 감사/로그 용 태그
    )

    return ImportS3Summary(
        scanned=scanned,
        imported=imported,
        skipped_existing=skipped,
        errors=errors,
        first_key=first_key,
        last_key=last_key,
    )
