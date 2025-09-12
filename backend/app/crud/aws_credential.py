# app/crud/credentials.py
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.aws_credential import AwsCredential  # 모델 파일을 분리했다면 경로에 맞게 수정
from app.schemas.aws_credential import AwsCredentialCreate, AwsCredentialUpdate


def _mask_access_key_id(access_key_id: Optional[str]) -> Optional[str]:
    if not access_key_id:
        return None
    return access_key_id[-4:].rjust(len(access_key_id), "*")


def get(db: Session, user_id: int, cred_id: int) -> AwsCredential:
    cred = db.execute(
        select(AwsCredential).where(
            AwsCredential.id == cred_id,
            AwsCredential.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return cred


def get_multi(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
    name_like: Optional[str] = None,
) -> List[AwsCredential]:
    stmt = select(AwsCredential).where(AwsCredential.user_id == user_id)
    if name_like:
        stmt = stmt.where(AwsCredential.name.ilike(f"%{name_like}%"))
    stmt = stmt.order_by(AwsCredential.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def create(db: Session, user_id: int, obj_in: AwsCredentialCreate) -> AwsCredential:
    cred = AwsCredential(
        user_id=user_id,
        name=obj_in.name,
        region=obj_in.region,
        is_active=obj_in.is_active,
        access_key_id=obj_in.access_key_id,
        secret_access_key=obj_in.secret_access_key,
    )
    db.add(cred)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # 유저 내 name 유니크 제약 위반
        raise HTTPException(status_code=409, detail="Credential name already exists")
    db.refresh(cred)
    return cred


def update(
    db: Session, user_id: int, cred_id: int, obj_in: AwsCredentialUpdate
) -> AwsCredential:
    cred = get(db, user_id, cred_id)

    if obj_in.name is not None:
        cred.name = obj_in.name
    if obj_in.region is not None:
        cred.region = obj_in.region
    if obj_in.is_active is not None:
        cred.is_active = obj_in.is_active
    if obj_in.access_key_id is not None:
        cred.access_key_id = obj_in.access_key_id
    if obj_in.secret_access_key is not None:
        cred.secret_access_key = obj_in.secret_access_key

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Credential name already exists")
    db.refresh(cred)
    return cred


def delete(db: Session, user_id: int, cred_id: int) -> None:
    cred = get(db, user_id, cred_id)
    db.delete(cred)
    db.commit()


def set_active(db: Session, user_id: int, cred_id: int, active: bool) -> AwsCredential:
    cred = get(db, user_id, cred_id)
    cred.is_active = active
    db.commit()
    db.refresh(cred)
    return cred


def touch_last_used(db: Session, user_id: int, cred_id: int) -> AwsCredential:
    from datetime import datetime

    cred = get(db, user_id, cred_id)
    cred.last_used_at = datetime.utcnow()
    db.commit()
    db.refresh(cred)
    return cred


# 직렬화 보조: 민감정보 숨기고 last4 제공
def to_out_dict(cred: AwsCredential) -> dict:
    d = {
        "id": cred.id,
        "user_id": cred.user_id,
        "name": cred.name,
        "region": cred.region,
        "is_active": cred.is_active,
        "created_at": cred.created_at,
        "updated_at": cred.updated_at,
        "last_used_at": cred.last_used_at,
        "access_key_id_last4": _mask_access_key_id(cred.access_key_id),
        "has_secret": bool(cred.secret_access_key),
    }
    return d
