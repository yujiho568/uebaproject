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
import time
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime
import json
import logging

logger = logging.getLogger("quarantine")
logger.setLevel(logging.INFO)

from app.db.database import get_db
from app.models.aws_credential import AwsCredential
from app.schemas.aws_credential import (
    AwsCredentialCreate,
    AwsCredentialUpdate,
    AwsCredentialOut,
)
from app.crud import aws_credential as crud


router = APIRouter(prefix="/credentials/{user_id}", tags=["credentials"])

# 모든 액션을 Deny하는 인라인 정책 (필요 시 수정 가능)
QUARANTINE_DENY_ALL = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyAll",
            "Effect": "Deny",
            "Action": "*",
            "Resource": "*"
        }
    ]
}


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
        
class QuarantineOut(BaseModel):
    applied: Optional[bool]                   # True=차단 / False=정상 / None=확인불가
    policy_name: str = "QuarantineDenyAll"
    account_id: Optional[str] = None
    account_name: Optional[str] = None

    # ★ 추가: 왜 확인불가/실패인지 알 수 있도록 이유 필드
    reason_code: Optional[str] = None         # e.g. "AccessDeniedException", "NoSuchEntity"
    reason_message: Optional[str] = None      # 짧은 설명
    # verbose=1 일 때만 채워줄 수 있는 원문(선택)
    error_raw: Optional[str] = None
    
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

def _is_quarantined(iam, user_name: str, policy_name: str, debug: bool = False) -> bool:
    """해당 IAM 유저에 policy_name이 인라인/관리형으로 붙었는지 확인"""
    try:
        attached = iam.list_attached_user_policies(UserName=user_name).get("AttachedPolicies", [])
        inline = iam.list_user_policies(UserName=user_name).get("PolicyNames", [])
        if debug:
            print(f"[VERIFY] attached({len(attached)}): {[p.get('PolicyName') for p in attached]}")
            print(f"[VERIFY] inline({len(inline)}): {inline}")
        if any(p.get("PolicyName") == policy_name for p in attached):
            return True
        if any(n == policy_name for n in inline):
            return True
        # 인라인 단건 확인 (권한 없으면 예외)
        try:
            iam.get_user_policy(UserName=user_name, PolicyName=policy_name)
            if debug:
                print(f"[VERIFY] get_user_policy('{policy_name}') returned OK")
            return True
        except Exception as e:
            if debug:
                print(f"[VERIFY] get_user_policy('{policy_name}') -> {type(e).__name__}: {e}")
            return False
    except Exception as e:
        if debug:
            print(f"[VERIFY] list policies failed: {type(e).__name__}: {e}")
        return False

def _verify_with_retry(check_fn, attempts=3, delay_ms=300, label: str = "") -> bool:
    for i in range(1, attempts+1):
        ok = check_fn()
        print(f"[VERIFY] attempt {i}/{attempts}{(' - ' + label) if label else ''}: {ok}")
        if ok:
            return True
        time.sleep(delay_ms / 1000.0)
    return False


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

# 변경: 항상 root 자격증명으로 확인하되, 오류가 나도 200으로 내려서 UI가 '확인불가'를 표시할 수 있게 함
@router.get("/{name}/quarantine", response_model=QuarantineOut)
def check_quarantine_for_credential(
    user_id: int = Path(..., ge=1),
    name: str = Path(..., min_length=1),
    policy_name: str = Query("QuarantineDenyAll"),
    verbose: int = Query(0, ge=0, le=1),                      # ★ 추가: 원문 노출 여부
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # root 키 사용 (회원가입 때 저장)
    root_user = db.query(User).filter(User.id == user_id).first()
    if not root_user or not root_user.aws_access_key or not root_user.aws_secret_key:
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="RootCredentialsMissing",
            reason_message="User has no stored root credentials",
        )

    try:
        iam = boto3.client(
            "iam",
            aws_access_key_id=root_user.aws_access_key,
            aws_secret_access_key=root_user.aws_secret_key,
        )

        # 1) IAM 유저 확인
        user_info = iam.get_user(UserName=name)
        user_arn = user_info["User"]["Arn"]

        # 2) 유저에 붙은 정책 조회 (관리형 + 인라인)
        attached = iam.list_attached_user_policies(UserName=name)["AttachedPolicies"]
        inline_names = iam.list_user_policies(UserName=name)["PolicyNames"]

        quarantined = any(p["PolicyName"] == policy_name for p in attached) \
            or any(p == policy_name for p in inline_names)

        return QuarantineOut(
            applied=quarantined,
            policy_name=policy_name,
            account_id=None,
            account_name=None,
        )

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return QuarantineOut(
            applied=None,                                 # 확인불가
            policy_name=policy_name,
            reason_code=code,                             # ★ 왜인지 볼 수 있게
            reason_message=msg[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )
    except Exception as e:
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="UnhandledException",
            reason_message=str(e)[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )

@router.post("/{name}/quarantine/apply", response_model=QuarantineOut)
def apply_quarantine_policy(
    user_id: int = Path(..., ge=1),
    name: str = Path(..., min_length=1),
    policy_name: str = Query("QuarantineDenyAll"),
    verbose: int = Query(0, ge=0, le=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    print(f"\n[APPLY] ==== START user_id={user_id} name='{name}' policy_name='{policy_name}' ====")

    root_user = db.query(User).filter(User.id == user_id).first()
    if not root_user or not root_user.aws_access_key or not root_user.aws_secret_key:
        print("[APPLY] Root credentials missing")
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="RootCredentialsMissing",
            reason_message="User has no stored root credentials",
        )

    # 루트 키 마스킹 출력
    ak = root_user.aws_access_key
    masked = f"{ak[:4]}{'*' * max(0, len(ak)-8)}{ak[-4:]}" if ak else "None"
    print(f"[APPLY] Using ROOT AccessKeyId(masked)={masked}")

    try:
        # STEP 1) IAM 클라이언트 & 대상 유저 확인
        iam = boto3.client(
            "iam",
            aws_access_key_id=root_user.aws_access_key,
            aws_secret_access_key=root_user.aws_secret_key,
        )
        user_info = iam.get_user(UserName=name)
        user_arn = user_info["User"]["Arn"]
        created = user_info["User"].get("CreateDate")
        print(f"[APPLY] STEP 1: get_user OK arn={user_arn} created={created}")

        # STEP 2) 현재 부착 정책 나열(참고)
        attached_before = iam.list_attached_user_policies(UserName=name).get("AttachedPolicies", [])
        inline_before = iam.list_user_policies(UserName=name).get("PolicyNames", [])
        print(f"[APPLY] STEP 2: before attached={ [p.get('PolicyName') for p in attached_before] }")
        print(f"[APPLY] STEP 2: before inline={ inline_before }")

        # STEP 3) put_user_policy 호출
        policy_doc = json.dumps(QUARANTINE_DENY_ALL)
        iam.put_user_policy(
            UserName=name,
            PolicyName=policy_name,
            PolicyDocument=policy_doc,
        )
        print(f"[APPLY] STEP 3: put_user_policy('{policy_name}') sent")

        # STEP 4) 재검증(재시도 포함)
        ok = _verify_with_retry(
            lambda: _is_quarantined(iam, name, policy_name, debug=bool(verbose)),
            attempts=3,
            delay_ms=400,
            label=f"name={name} policy={policy_name}",
        )
        if not ok:
            # 실패 시 직후 상태 스냅샷도 함께 출력
            attached_after = iam.list_attached_user_policies(UserName=name).get("AttachedPolicies", [])
            inline_after = iam.list_user_policies(UserName=name).get("PolicyNames", [])
            print(f"[APPLY] STEP 4: after attached={ [p.get('PolicyName') for p in attached_after] }")
            print(f"[APPLY] STEP 4: after inline={ inline_after }")
            print("[APPLY] VERIFICATION FAILED: policy not observed after retries")
            return QuarantineOut(
                applied=None,
                policy_name=policy_name,
                reason_code="ApplyVerificationFailed",
                reason_message="put_user_policy succeeded but policy not visible after retries",
            )

        print("[APPLY] STEP 4: verification OK -> applied=True")
        print(f"[APPLY] ==== DONE name='{name}' ====")
        return QuarantineOut(
            applied=True,
            policy_name=policy_name,
        )

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        msg = e.response.get("Error", {}).get("Message", str(e))
        print(f"[APPLY][ClientError] code={code} msg={msg}")
        if verbose:
            print(f"[APPLY][ClientError][raw] {e}")
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code=code,
            reason_message=msg[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )
    except Exception as e:
        print(f"[APPLY][Unhandled] {type(e).__name__}: {e}")
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="UnhandledException",
            reason_message=str(e)[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )



@router.delete("/{name}/quarantine", response_model=QuarantineOut)
def remove_quarantine_policy(
    user_id: int = Path(..., ge=1),
    name: str = Path(..., min_length=1),
    policy_name: str = Query("QuarantineDenyAll"),
    verbose: int = Query(0, ge=0, le=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    root_user = db.query(User).filter(User.id == user_id).first()
    if not root_user or not root_user.aws_access_key or not root_user.aws_secret_key:
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="RootCredentialsMissing",
            reason_message="User has no stored root credentials",
        )

    try:
        iam = boto3.client(
            "iam",
            aws_access_key_id=root_user.aws_access_key,
            aws_secret_access_key=root_user.aws_secret_key,
        )

        # 대상 유저 확인
        iam.get_user(UserName=name)

        # 인라인 정책 삭제 (존재하지 않으면 NoSuchEntity 가능)
        try:
            iam.delete_user_policy(UserName=name, PolicyName=policy_name)
        except ClientError as e:
            # 정책이 없었으면 OK로 처리
            if e.response.get("Error", {}).get("Code") != "NoSuchEntity":
                raise

        # ★ 해제 검증 (재시도 포함)
        ok = _verify_with_retry(lambda: not _is_quarantined(iam, name, policy_name))
        if not ok:
            return QuarantineOut(
                applied=None,
                policy_name=policy_name,
                reason_code="RemoveVerificationFailed",
                reason_message="delete_user_policy succeeded but policy still visible after retries",
            )

        return QuarantineOut(
            applied=False,
            policy_name=policy_name,
        )

    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code=code,
            reason_message=msg[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )
    except Exception as e:
        return QuarantineOut(
            applied=None,
            policy_name=policy_name,
            reason_code="UnhandledException",
            reason_message=str(e)[:200],
            error_raw=(str(e)[:2000] if verbose else None),
        )

