"""QuercusClient against a mocked Canvas API (no network)."""

import httpx
import pytest
import respx

from quercus_bot import client as client_mod
from quercus_bot.client import BASE_URL, QuercusClient


@pytest.fixture
def api():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def quercus():
    return QuercusClient(token="test-token")


async def test_get_active_courses_parses_response(api, quercus):
    api.get(f"{BASE_URL}/courses").respond(
        json=[{"id": 1, "name": "Deep Learning", "course_code": "APS360H1"}]
    )

    courses = await quercus.get_active_courses()

    assert [(c.id, c.course_code) for c in courses] == [(1, "APS360H1")]


async def test_bearer_token_is_sent(api, quercus):
    route = api.get(f"{BASE_URL}/courses").respond(json=[])

    await quercus.get_active_courses()

    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


async def test_401_raises_auth_error_instead_of_empty_list(api, quercus):
    api.get(f"{BASE_URL}/courses").respond(status_code=401)

    with pytest.raises(client_mod.QuercusAuthError):
        await quercus.get_active_courses()


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_server_error_raises_api_error(api, quercus, status):
    api.get(f"{BASE_URL}/announcements").respond(status_code=status)

    with pytest.raises(client_mod.QuercusAPIError):
        await quercus.get_announcements([1])


async def test_network_error_raises_api_error(api, quercus):
    api.get(f"{BASE_URL}/courses/1/assignments").mock(side_effect=httpx.ConnectError("down"))

    with pytest.raises(client_mod.QuercusAPIError):
        await quercus.get_assignments(1)


async def test_hidden_files_tab_returns_empty_list(api, quercus):
    """403 on /files means the instructor hid the tab; that is not an error."""
    api.get(f"{BASE_URL}/courses/1/files").respond(status_code=403)

    assert await quercus.get_course_files(1) == []


async def test_assignment_without_submission_or_due_date(api, quercus):
    api.get(f"{BASE_URL}/courses/1/assignments").respond(
        json=[{"id": 9, "name": "Reading", "due_at": None, "points_possible": None}]
    )

    [a] = await quercus.get_assignments(1)

    assert a.due_at is None and a.submission is None


def test_missing_token_is_rejected(monkeypatch):
    monkeypatch.delenv("QUERCUS_API_TOKEN", raising=False)
    monkeypatch.setattr(client_mod, "load_dotenv", lambda *a, **k: None)

    with pytest.raises(ValueError):
        QuercusClient()
