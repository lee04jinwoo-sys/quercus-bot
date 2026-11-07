"""Persistence and message formatting."""

from quercus_bot.models import HistoryStore
from quercus_bot.notifier import (
    clean_html,
    format_announcement_message,
    format_deadline_message,
)
from quercus_bot.storage import load_history, save_history
from tests.conftest import make_announcement, make_assignment


def test_history_round_trip(tmp_path):
    path = tmp_path / "h.json"
    store = HistoryStore(initialized=True, sent_announcements=[1, 2], sent_grades={"7": 8.5})

    save_history(store, path)

    assert load_history(path) == store


def test_missing_history_file_gives_fresh_store(tmp_path):
    assert load_history(tmp_path / "nope.json") == HistoryStore()


def test_corrupt_history_file_gives_fresh_store(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("{not json")

    assert load_history(path).initialized is False


def test_save_leaves_no_temp_file(tmp_path):
    path = tmp_path / "h.json"
    save_history(HistoryStore(), path)

    assert [p.name for p in tmp_path.iterdir()] == ["h.json"]


def test_clean_html_strips_tags_and_entities():
    assert clean_html("<p>Room&nbsp;A &amp; B</p><br/>Bring ID") == "Room\xa0A & B\n\nBring ID".strip()


def test_announcement_message_escapes_html_in_title():
    ann = make_announcement(title="<b>Quiz</b> & more")

    msg = format_announcement_message("APS360", ann)

    assert "<b>Quiz</b>" not in msg.split("제목:</b>")[1].split("\n")[0]
    assert "&lt;b&gt;Quiz&lt;/b&gt;" in msg


def test_long_announcement_is_truncated():
    ann = make_announcement()
    ann.message = "x" * 5000

    msg = format_announcement_message("APS360", ann)

    assert len(msg) < 1000
    assert msg.endswith("...")


def test_deadline_message_contains_name_and_type():
    a = make_assignment(hours_until_due=22)

    msg = format_deadline_message("APS360", a, "D-1", 22.0)

    assert "Lab 4" in msg and "D-1" in msg
