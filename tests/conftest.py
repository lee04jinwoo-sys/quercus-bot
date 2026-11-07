"""Shared fixtures: a fake Quercus client and an in-memory Telegram sender."""

from datetime import datetime, timedelta, timezone

import pytest

from quercus_bot import daemon
from quercus_bot.models import Announcement, Assignment, Course, CourseFile, Submission


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """check_once() writes sent_history.json into the CWD; keep it in tmp."""
    monkeypatch.chdir(tmp_path)


class FakeClient:
    """Duck-typed stand-in for QuercusClient. Set attributes to script responses."""

    def __init__(self):
        self.courses = [Course(id=1, name="APS360 Deep Learning", course_code="APS360H1")]
        self.announcements: list[Announcement] = []
        self.assignments: list[Assignment] = []
        self.files: list[CourseFile] = []
        self.raise_on: dict[str, Exception] = {}

    def _maybe_raise(self, name):
        if name in self.raise_on:
            raise self.raise_on[name]

    async def get_active_courses(self):
        self._maybe_raise("courses")
        return self.courses

    async def get_announcements(self, course_ids, start_date=None):
        self._maybe_raise("announcements")
        return self.announcements

    async def get_assignments(self, course_id):
        self._maybe_raise("assignments")
        return self.assignments

    async def get_course_files(self, course_id, limit=15):
        self._maybe_raise("files")
        return self.files


class Telegram:
    """Records messages; `ok` toggles simulated delivery failure."""

    def __init__(self):
        self.sent: list[str] = []
        self.ok = True

    async def __call__(self, text, *args, **kwargs):
        if not self.ok:
            return False
        self.sent.append(text)
        return True


@pytest.fixture
def client():
    return FakeClient()


@pytest.fixture
def telegram(monkeypatch):
    tg = Telegram()
    monkeypatch.setattr(daemon, "send_telegram_message", tg)
    return tg


def make_announcement(id_=100, title="Midterm room change"):
    return Announcement(
        id=id_,
        title=title,
        message="<p>Room is now EX310</p>",
        posted_at=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        context_code="course_1",
    )


def make_assignment(id_=7, hours_until_due=None, state="unsubmitted", score=None):
    due = (
        datetime.now(timezone.utc) + timedelta(hours=hours_until_due)
        if hours_until_due is not None
        else None
    )
    return Assignment(
        id=id_,
        name="Lab 4",
        due_at=due,
        course_id=1,
        points_possible=10,
        submission=Submission(workflow_state=state, score=score),
    )


def make_file(id_=55, name="lecture07.pdf"):
    return CourseFile(
        id=id_,
        display_name=name,
        updated_at=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
        size=1_048_576,
    )
