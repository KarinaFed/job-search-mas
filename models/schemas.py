"""Pydantic schemas for data models."""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SeniorityLevel(str, Enum):
    """Seniority levels."""
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"


class MobilityLevel(str, Enum):
    """Geographic mobility levels."""
    NONE = "none"
    LOCAL = "local"
    REGIONAL = "regional"
    NATIONAL = "national"
    INTERNATIONAL = "international"


class ApplicationStatus(str, Enum):
    """Application status."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VIEWED = "viewed"
    INTERVIEW = "interview"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class Skill(BaseModel):
    """Skill representation."""
    name: str
    level: Optional[str] = None
    years_experience: Optional[float] = None


class Profile(BaseModel):
    """User profile schema."""
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    resume_text: str
    skills: List[Skill] = []
    seniority: SeniorityLevel = SeniorityLevel.MIDDLE
    mobility: MobilityLevel = MobilityLevel.LOCAL
    location: Optional[str] = None
    salary_expectations: Optional[int] = None
    career_objectives: Optional[str] = None
    preferred_industries: List[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class JobPosting(BaseModel):
    """Job posting schema."""
    job_id: str
    title: str
    company: str
    description: str
    requirements: List[str] = []
    skills_required: List[str] = []
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    seniority_level: Optional[SeniorityLevel] = None
    url: Optional[str] = None
    source: str = "hh.ru"
    posted_at: Optional[datetime] = None
    relevance_score: Optional[float] = None


class JobMatch(BaseModel):
    """Job match with relevance score."""
    job: JobPosting
    relevance_score: float = Field(ge=0.0, le=1.0)
    match_reasons: List[str] = []
    gaps: List[str] = []


class Application(BaseModel):
    """Job application schema."""
    application_id: str
    user_id: str
    job_id: str
    status: ApplicationStatus = ApplicationStatus.DRAFT
    cover_letter: Optional[str] = None
    adapted_resume: Optional[str] = None
    submitted_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    interview_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Strategy(BaseModel):
    """Job search strategy."""
    strategy_id: str
    user_id: str
    objectives: List[str] = []
    target_positions: List[str] = []
    target_companies: List[str] = []
    priority_skills: List[str] = []
    timeline: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class KPIMetrics(BaseModel):
    """KPI metrics for job search."""
    user_id: str
    period_start: datetime
    period_end: datetime
    total_applications: int = 0
    applications_viewed: int = 0
    interviews_scheduled: int = 0
    offers_received: int = 0
    average_relevance_score: float = 0.0
    click_through_rate: float = 0.0
    interview_rate: float = 0.0
    offer_rate: float = 0.0


class AgentMessage(BaseModel):
    """Message between agents."""
    message_id: str
    from_agent: str
    to_agent: Optional[str] = None
    message_type: str
    content: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str


class TaskRequest(BaseModel):
    """Task request for the MAS."""
    user_id: str
    task_type: str
    input_data: Dict[str, Any]
    session_id: Optional[str] = None


class TaskResponse(BaseModel):
    """Task response from the MAS."""
    task_id: str
    session_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    agent_trace: List[str] = []
