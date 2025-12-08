"""Database models and connection."""
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
from config import settings

Base = declarative_base()


class ProfileDB(Base):
    """Profile database model."""
    __tablename__ = "profiles"
    
    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    resume_text = Column(Text)
    skills = Column(JSON)
    seniority = Column(String)
    mobility = Column(String)
    location = Column(String, nullable=True)
    salary_expectations = Column(Integer, nullable=True)
    career_objectives = Column(Text, nullable=True)
    preferred_industries = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    applications = relationship("ApplicationDB", back_populates="profile")
    strategies = relationship("StrategyDB", back_populates="profile")


class JobPostingDB(Base):
    """Job posting database model."""
    __tablename__ = "job_postings"
    
    job_id = Column(String, primary_key=True)
    title = Column(String)
    company = Column(String)
    description = Column(Text)
    requirements = Column(JSON)
    skills_required = Column(JSON)
    location = Column(String, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    seniority_level = Column(String, nullable=True)
    url = Column(String, nullable=True)
    source = Column(String, default="hh.ru")
    posted_at = Column(DateTime, nullable=True)
    relevance_score = Column(Float, nullable=True)
    embedding = Column(Text, nullable=True)
    
    applications = relationship("ApplicationDB", back_populates="job")


class ApplicationDB(Base):
    """Application database model."""
    __tablename__ = "applications"
    
    application_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("profiles.user_id"))
    job_id = Column(String, ForeignKey("job_postings.job_id"))
    status = Column(String, default="draft")
    cover_letter = Column(Text, nullable=True)
    adapted_resume = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    viewed_at = Column(DateTime, nullable=True)
    interview_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    profile = relationship("ProfileDB", back_populates="applications")
    job = relationship("JobPostingDB", back_populates="applications")


class StrategyDB(Base):
    """Strategy database model."""
    __tablename__ = "strategies"
    
    strategy_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("profiles.user_id"))
    objectives = Column(JSON)
    target_positions = Column(JSON)
    target_companies = Column(JSON)
    priority_skills = Column(JSON)
    timeline = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    profile = relationship("ProfileDB", back_populates="strategies")


DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
