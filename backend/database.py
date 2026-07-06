"""
Database configuration — supports SQLite (dev) and PostgreSQL (production).
Set DATABASE_URL env var to switch: postgresql+psycopg2://user:pass@host/dbname
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite needs check_same_thread=False; PostgreSQL does not need it
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,       # detect stale connections
    echo=settings.DEBUG,      # SQL logging in debug mode
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
