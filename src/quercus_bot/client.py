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


class QuercusAPIError(Exception):
    """The Canvas API could not be reached or returned an error status.

    Raised instead of returning an empty list so callers can tell
    "no news" apart from "could not check".
    """


class QuercusAuthError(QuercusAPIError):
    """The API token was rejected (HTTP 401). Needs a human to renew it."""


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_api_error(url: str, exc: httpx.HTTPError) -> QuercusAPIError:
    """Build a QuercusAPIError with a short description that never includes the token."""
    if isinstance(exc, httpx.HTTPStatusError):
        return QuercusAPIError(f"HTTP {exc.response.status_code} for {url}")
    return QuercusAPIError(f"{type(exc).__name__} for {url}")


class QuercusClient:
    """Async client interacting with U of T Quercus (Canvas LMS) REST API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("QUERCUS_API_TOKEN")
        if not self.token:
            raise ValueError("QUERCUS_API_TOKEN is required in .env or environment")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.timeout = httpx.Timeout(15.0, connect=10.0)

    async def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        """GET a Canvas endpoint, translating failures into QuercusAPIError."""
        async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise QuercusAuthError(f"HTTP 401 for {url}") from exc
                raise _to_api_error(url, exc) from exc
            except httpx.HTTPError as exc:
                raise _to_api_error(url, exc) from exc

    async def get_active_courses(self) -> list[Course]:
        """Fetch all currently enrolled active courses."""
        data = await self._get_json(
            f"{BASE_URL}/courses", {"enrollment_state": "active", "per_page": 50}
        )
        return [
            Course(
                id=item["id"],
                name=item.get("name", "Unknown"),
                course_code=item.get("course_code"),
            )
            for item in data
        ]

    async def get_announcements(
        self, course_ids: Sequence[int], start_date: Optional[datetime] = None
    ) -> list[Announcement]:
        """Fetch announcements for specified courses."""
        if not course_ids:
            return []

        params: dict[str, Any] = {
            "context_codes[]": [f"course_{cid}" for cid in course_ids],
            "per_page": 30,
        }
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")

        data = await self._get_json(f"{BASE_URL}/announcements", params)
        return [
            Announcement(
                id=item["id"],
                title=item.get("title", ""),
                message=item.get("message", ""),
                posted_at=_parse_dt(item["posted_at"]),
                context_code=item.get("context_code", ""),
                url=item.get("url"),
            )
            for item in data
        ]

    async def get_assignments(self, course_id: int) -> list[Assignment]:
        """Fetch all assignments including user submission status for a course."""
        data = await self._get_json(
            f"{BASE_URL}/courses/{course_id}/assignments",
            {"include[]": "submission", "per_page": 50, "order_by": "due_at"},
        )
        assignments: list[Assignment] = []
        for item in data:
            sub_raw = item.get("submission")
            submission = None
            if sub_raw:
                submission = Submission(
                    workflow_state=sub_raw.get("workflow_state", "unsubmitted"),
                    score=sub_raw.get("score"),
                    grade=sub_raw.get("grade"),
                    submitted_at=(
                        _parse_dt(sub_raw["submitted_at"]) if sub_raw.get("submitted_at") else None
                    ),
                )
            assignments.append(
                Assignment(
                    id=item["id"],
                    name=item.get("name", "Unnamed Assignment"),
                    due_at=_parse_dt(item["due_at"]) if item.get("due_at") else None,
                    course_id=course_id,
                    points_possible=item.get("points_possible"),
                    submission=submission,
                    html_url=item.get("html_url"),
                )
            )
        return assignments

    async def get_course_files(self, course_id: int, limit: int = 15) -> list[CourseFile]:
        """Fetch recently uploaded files for a course.

        A 403 means the instructor hid the Files tab; that is not an error.
        """
        try:
            data = await self._get_json(
                f"{BASE_URL}/courses/{course_id}/files",
                {"sort": "updated_at", "order": "desc", "per_page": limit},
            )
        except QuercusAuthError:
            raise
        except QuercusAPIError as exc:
            cause = exc.__cause__
            if isinstance(cause, httpx.HTTPStatusError) and cause.response.status_code == 403:
                logger.debug(f"Files tab is hidden for course {course_id} (403 Forbidden).")
                return []
            raise
        return [
            CourseFile(
                id=item["id"],
                display_name=item.get("display_name", "Unknown File"),
                updated_at=_parse_dt(item["updated_at"]),
                size=item.get("size"),
                url=item.get("url"),
            )
            for item in data
        ]
