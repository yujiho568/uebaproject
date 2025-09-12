# app/schemas/results.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ImportS3Request(BaseModel):
    # 저장된 credential 선택용
    credential_name: str = "default"
    bucket: str
    prefix: str  # 예: "results/realtime/2025/09/11/"
    region: str = "ap-northeast-2"
    max_files: Optional[int] = Field(None, ge=1, description="처리 상한(옵션)")
    dry_run: bool = False

class ImportS3Summary(BaseModel):
    scanned: int
    imported: int
    skipped_existing: int
    errors: int
    first_key: Optional[str] = None
    last_key: Optional[str] = None
