"""Behavioral tests for check_once(): sync, dedupe, deadlines, failure handling."""

import pytest

from quercus_bot import client as client_mod
from quercus_bot.daemon import check_once
from quercus_bot.models import HistoryStore
from tests.conftest import make_announcement, make_assignment, make_file


def initialized_store() -> HistoryStore:
    return HistoryStore(initialized=True)


# --- initial sync ----------------------------------------------------------


async def test_initial_sync_indexes_without_alerting(client, telegram):
    client.announcements = [make_announcement()]
    client.files = [make_file()]
    client.assignments = [make_assignment(score=8.0, state="graded")]
    store = HistoryStore()

    sent = await check_once(client, store)

    assert sent == 0
    assert telegram.sent == []
    assert store.initialized is True
    assert store.sent_announcements == [100]
    assert store.sent_files == [55]
    assert store.sent_grades == {"7": 8.0}


# --- new items after initialization ---------------------------------------


async def test_new_announcement_alerts_exactly_once(client, telegram):
    store = initialized_store()
    client.announcements = [make_announcement()]

    first = await check_once(client, store)
    second = await check_once(client, store)

    assert first == 1
    assert second == 0
    assert len(telegram.sent) == 1
    assert "Midterm room change" in telegram.sent[0]


async def test_new_grade_alerts_once(client, telegram):
    store = initialized_store()
    client.assignments = [make_assignment(state="graded", score=9.5)]

    await check_once(client, store)
    await check_once(client, store)

    assert len(telegram.sent) == 1
    assert "9.5" in telegram.sent[0]


async def test_new_file_alerts_once(client, telegram):
    store = initialized_store()
    client.files = [make_file()]

    await check_once(client, store)
    await check_once(client, store)

    assert len(telegram.sent) == 1
    assert "lecture07.pdf" in telegram.sent[0]


# --- deadline windows ------------------------------------------------------


@pytest.mark.parametrize(
    "hours_left, expected",
    [
        (60, "D-3"),
        (22, "D-1"),
        (10, "D-Day (12시간 전)"),
        (2, "D-Day (마감 직전)"),
    ],
)
async def test_deadline_alert_windows(client, telegram, hours_left, expected):
    store = initialized_store()
    client.assignments = [make_assignment(hours_until_due=hours_left)]

    await check_once(client, store)

    assert len(telegram.sent) == 1
    assert expected in telegram.sent[0]


@pytest.mark.parametrize("hours_left", [100, 40, 15, -1])
async def test_no_deadline_alert_outside_windows(client, telegram, hours_left):
    store = initialized_store()
    client.assignments = [make_assignment(hours_until_due=hours_left)]

    await check_once(client, store)

    assert telegram.sent == []


async def test_deadline_alert_not_repeated(client, telegram):
    store = initialized_store()
    client.assignments = [make_assignment(hours_until_due=22)]

    await check_once(client, store)
    await check_once(client, store)

    assert len(telegram.sent) == 1


async def test_submitted_assignment_gets_no_deadline_alert(client, telegram):
    store = initialized_store()
    client.assignments = [make_assignment(hours_until_due=22, state="submitted")]

    await check_once(client, store)

    assert telegram.sent == []


async def test_deadline_alert_retried_after_failed_send(client, telegram):
    store = initialized_store()
    client.assignments = [make_assignment(hours_until_due=22)]

    telegram.ok = False
    await check_once(client, store)
    telegram.ok = True
    await check_once(client, store)

    assert len(telegram.sent) == 1


# --- delivery failure must not swallow alerts -----------------------------


@pytest.mark.parametrize(
    "kind",
    ["announcement", "grade", "file"],
)
async def test_failed_send_is_retried_next_run(client, telegram, kind):
    """A Telegram outage must not permanently drop an alert."""
    store = initialized_store()
    if kind == "announcement":
        client.announcements = [make_announcement()]
    elif kind == "grade":
        client.assignments = [make_assignment(state="graded", score=7.0)]
    else:
        client.files = [make_file()]

    telegram.ok = False
    await check_once(client, store)
    assert telegram.sent == []

    telegram.ok = True
    await check_once(client, store)
    assert len(telegram.sent) == 1


# --- Quercus API failure handling ------------------------------------------


async def test_api_failure_during_initial_sync_does_not_finish_sync(client, telegram):
    """If the first sync is incomplete, the next run must not flood old items."""
    store = HistoryStore()
    client.announcements = [make_announcement()]
    client.raise_on["announcements"] = client_mod.QuercusAPIError("HTTP 500")

    sent = await check_once(client, store)

    assert sent == 0
    assert store.initialized is False

    client.raise_on.clear()
    await check_once(client, store)

    assert telegram.sent == []  # old announcement indexed silently, no flood
    assert store.initialized is True


async def test_auth_failure_alerts_once_not_every_poll(client, telegram):
    store = initialized_store()
    client.raise_on["courses"] = client_mod.QuercusAuthError("HTTP 401")

    await check_once(client, store)
    await check_once(client, store)
    await check_once(client, store)

    assert len(telegram.sent) == 1
    assert "토큰" in telegram.sent[0]


async def test_auth_alert_rearms_after_recovery(client, telegram):
    store = initialized_store()
    client.raise_on["courses"] = client_mod.QuercusAuthError("HTTP 401")
    await check_once(client, store)

    client.raise_on.clear()
    await check_once(client, store)
    client.raise_on["courses"] = client_mod.QuercusAuthError("HTTP 401")
    await check_once(client, store)

    assert len(telegram.sent) == 2


async def test_non_auth_api_error_is_not_reported_as_no_news(client, telegram):
    store = initialized_store()
    client.raise_on["courses"] = client_mod.QuercusAPIError("HTTP 503")

    sent = await check_once(client, store)

    assert sent == 0
    assert store.last_check_at is None  # a failed poll is not a completed check
