import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

def _default_db_path() -> str:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(repo_root, "data", "ap_research.db")


def _resolve_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if isinstance(db_url, str) and db_url.strip():
        return db_url.strip()

    db_path = os.getenv("DB_PATH")
    if not isinstance(db_path, str) or not db_path.strip():
        db_path = _default_db_path()

    db_path = db_path.strip()
    if db_path.startswith("sqlite:"):
        return db_path

    abs_path = os.path.abspath(db_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    return f"sqlite:///{abs_path}"


SQLALCHEMY_DATABASE_URL = _resolve_database_url()

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
