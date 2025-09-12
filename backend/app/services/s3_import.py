# app/services/s3_import.py
import json
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.aws_credential import AwsCredential
from app.models.ueba_result import UebaResult

def get_stored_credentials(db: Session, user_id: int, credential_name: str) -> AwsCredential:
    cred = (
        db.query(AwsCredential)
          .filter(AwsCredential.user_id == user_id, AwsCredential.name == credential_name)
          .first()
    )
    if not cred:
        raise ValueError(f"Credential not found: name={credential_name}")
    return cred

def make_s3_client(region: str, access_key_id: str, secret_access_key: str):
    cfg = Config(
        region_name=region,
        read_timeout=20,
        connect_timeout=10,
        retries={"max_attempts": 5, "mode": "standard"},
    )
    return boto3.client(
        "s3",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=cfg,
    )

def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def map_payload_to_model(
    user_id: int,
    bucket: str,
    key: str,
    last_modified: Optional[datetime],
    payload: Dict[str, Any],
    source_credential_name: Optional[str] = None,  # ← 추가
) -> UebaResult:
    result = payload.get("result", {}) or {}
    return UebaResult(
        user_id=user_id,
        source_credential_name=source_credential_name,  # ← 추가
        s3_bucket=bucket,
        s3_key=key,
        s3_last_modified=last_modified,
        user_id_str=payload.get("userId"),
        timestamp=_parse_iso(payload.get("timestamp")),
        event_name=payload.get("eventName"),
        initial_session=payload.get("initial_session"),
        embedding_dim=payload.get("embedding_dim"),
        engine=result.get("engine"),
        cluster=result.get("cluster"),
        is_noise=result.get("is_noise"),
        nearest_dist=result.get("nearest_dist"),
        eps=result.get("eps"),
        r=result.get("r"),
        risk=result.get("risk"),
        raw_json=json.dumps(payload, ensure_ascii=False),
    )

def import_s3_jsons(
    db: Session,
    user_id: int,
    bucket: str,
    prefix: str,
    region: str,
    access_key_id: str,
    secret_access_key: str,
    credential_name: Optional[str] = None,
    max_files: Optional[int] = None,
    dry_run: bool = False,
) -> Tuple[int, int, int, int, Optional[str], Optional[str]]:
    """
    Returns: scanned, imported, skipped_existing, errors, first_key, last_key
    """
    s3 = make_s3_client(region, access_key_id, secret_access_key)
    paginator = s3.get_paginator("list_objects_v2")
    page_it = paginator.paginate(Bucket=bucket, Prefix=prefix)

    scanned = imported = skipped = errors = 0
    first_key = last_key = None

    batch = []
    BATCH_SIZE = 100

    def flush_batch():
        nonlocal imported, skipped, errors, batch
        for rec in batch:
            # idempotent insert: Unique(s3_bucket, s3_key)
            try:
                db.add(rec)
                db.commit()
                imported += 1
            except IntegrityError:
                db.rollback()
                skipped += 1
            except Exception:
                db.rollback()
                errors += 1
        batch = []

    for page in page_it:
        contents = page.get("Contents", [])
        for obj in contents:
            key = obj["Key"]
            if not key.lower().endswith(".json"):
                continue

            scanned += 1
            first_key = first_key or key
            last_key = key

            # max_files 제한
            if max_files and scanned > max_files:
                break

            try:
                # 다운로드 & 파싱
                o = s3.get_object(Bucket=bucket, Key=key)
                body = o["Body"].read()
                payload = json.loads(body)

                if dry_run:
                    continue

                rec = map_payload_to_model(
    user_id=user_id,
    bucket=bucket,
    key=key,
    last_modified=obj.get("LastModified"),
    payload=payload,
    source_credential_name=credential_name,  # ← 이 값을 import_s3_jsons의 인자로 추가
)

                batch.append(rec)

                if len(batch) >= BATCH_SIZE:
                    flush_batch()

            except ClientError:
                errors += 1
            except json.JSONDecodeError:
                errors += 1
            except Exception:
                errors += 1

        if max_files and scanned >= max_files:
            break

    if not dry_run and batch:
        flush_batch()

    return scanned, imported, skipped, errors, first_key, last_key
