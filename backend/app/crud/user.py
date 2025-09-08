from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.user import User
from app.schemas.user import UserCreate
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_email(db: Session, email: str):
    normalized = (email or "").strip().lower()
    return db.query(User).filter(func.lower(User.email) == normalized).first()

def create_user(db: Session, user: UserCreate):
    normalized_email = (user.email or "").strip().lower()
    hashed_password = pwd_context.hash(user.password)
    db_user = User(email=normalized_email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first() 