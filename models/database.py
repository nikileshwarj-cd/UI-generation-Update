"""
models/database.py
SQLAlchemy Database Engine for Local Embedded SQLite Database (code_gene.db).
Saved in UI-frontend root.
"""
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Embedded local database path in UI-frontend
DB_PATH = Path(__file__).parent.parent / "code_gene.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ProjectDB(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    framework = Column(String(50), default="React")
    language = Column(String(50), default="TypeScript")
    css_strategy = Column(String(50), default="Separate")
    folder_structure = Column(String(50), default="Feature-based")
    created_at = Column(DateTime, default=datetime.utcnow)

    stories = relationship("UserStoryDB", back_populates="project", cascade="all, delete-orphan")
    files = relationship("CodeFileDB", back_populates="project", cascade="all, delete-orphan")

class UserStoryDB(Base):
    __tablename__ = "user_stories"

    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    story_code = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    component_name = Column(String(100), nullable=False)
    depends_on_json = Column(Text, default="[]")

    project = relationship("ProjectDB", back_populates="stories")

class CodeFileDB(Base):
    __tablename__ = "code_files"

    id = Column(String(36), primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)

    project = relationship("ProjectDB", back_populates="files")

def init_db():
    """Initializes tables and seeds default project data if empty."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(ProjectDB).count() == 0:
            seed_initial_projects(db)
    finally:
        db.close()

def seed_initial_projects(db):
    pass

init_db()
