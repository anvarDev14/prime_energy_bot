from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Boolean, Float
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    moysklad_id = Column(String(100), nullable=True)
    role = Column(String(20), default="user")  # user | master | admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    status = Column(String(20), default="draft")  # draft | approved | rejected | published
    channel_message_id = Column(Integer, nullable=True)
    admin_id = Column(BigInteger, nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(BigInteger, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending | processing | done
    result_post_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MasterQuestion(Base):
    __tablename__ = "master_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BonusLog(Base):
    __tablename__ = "bonus_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False)
    phone = Column(String(20), nullable=False)
    bonus_points = Column(Float, default=0)
    checked_at = Column(DateTime, default=datetime.utcnow)
