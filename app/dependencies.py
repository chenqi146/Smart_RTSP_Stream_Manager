"""FastAPI 依赖注入模块"""
from typing import Generator
from db import SessionLocal


def get_db() -> Generator:
    """
    数据库会话依赖注入
    使用示例：
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

