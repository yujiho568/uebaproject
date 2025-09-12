# app/api/v1/endpoints/results.py
from fastapi import APIRouter, Path, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.results import ImportS3Request, ImportS3Summary
from app.services.s3_import import get_stored_credentials, import_s3_jsons

router = APIRouter(prefix="/results/{user_id}", tags=["results"])

@router.post("/import-s3", response_model=ImportS3Summary)
def import_from_s3(
    payload: ImportS3Request,
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    저장된 Credential(name으로 선택)을 사용해 S3의 JSON들을 가져와 DB(ueba_results)에 적재합니다.
    - idempotent: 동일 (bucket,key) 는 unique 제약으로 스킵
    - dry_run=True 이면 다운로드/파싱만 검증하고 DB에는 쓰지 않음
    """
    try:
        cred = get_stored_credentials(db, user_id, payload.credential_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    scanned, imported, skipped, errors, first_key, last_key = import_s3_jsons(
        db=db,
        user_id=user_id,
        bucket=payload.bucket,
        prefix=payload.prefix,
        region=payload.region or (cred.region or "ap-northeast-2"),
        access_key_id=cred.access_key_id,
        secret_access_key=cred.secret_access_key,
        max_files=payload.max_files,
        dry_run=payload.dry_run,
        credential_name=payload.credential_name,  # ← 추가
    )

    return ImportS3Summary(
        scanned=scanned,
        imported=imported,
        skipped_existing=skipped,
        errors=errors,
        first_key=first_key,
        last_key=last_key,
    )
