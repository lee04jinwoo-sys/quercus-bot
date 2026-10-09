"""Asynchronous Quercus Canvas REST API client."""

import logging
import os
from datetime import datetime
from typing import Any, Optional, Sequence
import httpx
from dotenv import load_dotenv

from quercus_bot.models import Announcement, Assignment, Course, CourseFile, Submission

load_dotenv()

logger = logging.getLogger("quercus_bot.client")

BASE_URL = "https://q.utoronto.ca/api/v1"


class QuercusClient:
    """Async client interacting with U of T Quercus (Canvas LMS) REST API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("QUERCUS_API_TOKEN")
        if not self.token:
            raise ValueError("QUERCUS_API_TOKEN is required in .env or environment")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.timeout = httpx.Timeout(15.0, connect=10.0)

    async def get_active_courses(self) -> list[Course]:
        """Fetch all currently enrolled active courses."""
        url = f"{BASE_URL}/courses"
        params = {"enrollment_state": "active", "per_page": 50}

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                courses: list[Course] = []
                for item in data:
                    courses.append(
                        Course(
                            id=item["id"],
                            name=item.get("name", "Unknown"),
                            course_code=item.get("course_code"),
                        )
                    )
                return courses
            except httpx.HTTPError as exc:
                logger.error(f"Failed to fetch active courses: {exc}")
                return []

    async def get_announcements(
        self, course_ids: Sequence[int], start_date: Optional[datetime] = None
    ) -> list[Announcement]:
        """Fetch announcements for specified courses."""
        if not course_ids:
            return []

        url = f"{BASE_URL}/announcements"
        params: dict[str, Any] = {
            "context_codes[]": [f"course_{cid}" for cid in course_ids],
            "per_page": 30,
        }
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                announcements: list[Announcement] = []
                for item in data:
                    announcements.append(
                        Announcement(
                            id=item["id"],
                            title=item.get("title", ""),
                            message=item.get("message", ""),
                            posted_at=datetime.fromisoformat(item["posted_at"].replace("Z", "+00:00")),
                            context_code=item.get("context_code", ""),
                            url=item.get("url"),
                        )
                    )
                return announcements
            except httpx.HTTPError as exc:
                logger.error(f"Failed to fetch announcements: {exc}")
                return []

    async def get_assignments(self, course_id: int) -> list[Assignment]:
        """Fetch all assignments including user submission status for a course."""
        url = f"{BASE_URL}/courses/{course_id}/assignments"
        params = {
            "include[]": "submission",
            "per_page": 50,
            "order_by": "due_at",
        }

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                assignments: list[Assignment] = []
                for item in data:
                    sub_raw = item.get("submission")
                    submission = None
                    if sub_raw:
                        submitted_at = (
                            datetime.fromisoformat(sub_raw["submitted_at"].replace("Z", "+00:00"))
                            if sub_raw.get("submitted_at")
                            else None
                        )
                        submission = Submission(
                            workflow_state=sub_raw.get("workflow_state", "unsubmitted"),
                            score=sub_raw.get("score"),
                            grade=sub_raw.get("grade"),
                            submitted_at=submitted_at,
                        )

                    due_at = (
                        datetime.fromisoformat(item["due_at"].replace("Z", "+00:00"))
                        if item.get("due_at")
                        else None
                    )

                    assignments.append(
                        Assignment(
                            id=item["id"],
                            name=item.get("name", "Unnamed Assignment"),
                            due_at=due_at,
                            course_id=course_id,
                            points_possible=item.get("points_possible"),
                            submission=submission,
                            html_url=item.get("html_url"),
                        )
                    )
                return assignments
            except httpx.HTTPError as exc:
                logger.error(f"Failed to fetch assignments for course {course_id}: {exc}")
                return []

    async def get_course_files(self, course_id: int, limit: int = 15) -> list[CourseFile]:
        """Fetch recently uploaded files for a course."""
        url = f"{BASE_URL}/courses/{course_id}/files"
        params = {
            "sort": "updated_at",
            "order": "desc",
            "per_page": limit,
        }

        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
                files: list[CourseFile] = []
                for item in data:
                    files.append(
                        CourseFile(
                            id=item["id"],
                            display_name=item.get("display_name", "Unknown File"),
                            updated_at=datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00")),
                            size=item.get("size"),
                            url=item.get("url"),
                        )
                    )
                return files
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403:
                    logger.debug(f"Files tab is hidden for course {course_id} (403 Forbidden).")
                else:
                    logger.warning(f"Failed to fetch files for course {course_id}: {exc}")
                return []
            except httpx.HTTPError as exc:
                logger.error(f"Failed to fetch files for course {course_id}: {exc}")
                return []
