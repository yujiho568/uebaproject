from fastapi import FastAPI
from app.api.v1.routers import api_router
from app.db.database import Base, engine
from pydantic_settings import BaseSettings
from pydantic import Field

app = FastAPI(title="UEBA System Backend")

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

# 라우터 등록
app.include_router(api_router, prefix="/api/v1") 