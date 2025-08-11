from __future__ import annotations
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'app_data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'ocr_results.sqlite3')

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class OcrResult(Base):
    __tablename__ = 'ocr_results'
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(512), nullable=False)
    processed_image_path = Column(String(512), nullable=True)
    date_text = Column(String(128), nullable=True)
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    det_boxes_json = Column(Text, nullable=True)


class AppConfig(Base):
    __tablename__ = 'app_config'
    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()


