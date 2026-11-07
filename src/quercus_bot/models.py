"""Pydantic models for Quercus API entities and state persistence."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class Course(BaseModel):
    id: int
    name: str
    course_code: Optional[str] = None


class Announcement(BaseModel):
    id: int
    title: str
    message: str
    posted_at: datetime
    context_code: str
    url: Optional[str] = None


class Submission(BaseModel):
    workflow_state: str = "unsubmitted"
    score: Optional[float] = None
    grade: Optional[str] = None
    submitted_at: Optional[datetime] = None


class Assignment(BaseModel):
    id: int
    name: str
    due_at: Optional[datetime] = None
    course_id: int
    points_possible: Optional[float] = None
    submission: Optional[Submission] = None
    html_url: Optional[str] = None


class CourseFile(BaseModel):
    id: int
    display_name: str
    updated_at: datetime
    size: Optional[int] = None
    url: Optional[str] = None


class HistoryStore(BaseModel):
    """Stores IDs and statuses of already notified items to prevent duplicates."""

    initialized: bool = False
    sent_announcements: list[int] = Field(default_factory=list)
    sent_grades: dict[str, Optional[float]] = Field(default_factory=dict)
    sent_due_alerts: dict[str, list[str]] = Field(default_factory=dict)
    sent_files: list[int] = Field(default_factory=list)
    auth_alert_sent: bool = False
    last_check_at: Optional[datetime] = None
