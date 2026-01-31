from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

engine_url = settings.get_engine_url()
engine = create_engine(
    engine_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,       # 默认5太小，提升以支持并行任务
    max_overflow=40,    # 允许额外连接，避免高并发时超时
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

