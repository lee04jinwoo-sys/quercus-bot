"""Background daemon and check logic for Quercus Bot."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from rich.logging import RichHandler

from quercus_bot.client import QuercusAPIError, QuercusAuthError, QuercusClient
from quercus_bot.models import Course, HistoryStore
from quercus_bot.notifier import (
    format_announcement_message,
    format_deadline_message,
    format_grade_message,
    format_new_file_message,
    send_telegram_message,
)
from quercus_bot.storage import load_history, save_history

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logger = logging.getLogger("quercus_bot.daemon")

COURSE_ALIAS_MAP: dict[str, str] = {
    "APS360": "APS360 (응용 딥러닝)",
    "CHE211": "CHE211 (유체역학)",
    "CLA204": "CLA204 (고전 신화)",
    "MIE375": "MIE375 (금융공학)",
}


def get_clean_course_name(course: Course) -> str:
    """Generate a clean, readable name for a course."""
    for prefix, clean_name in COURSE_ALIAS_MAP.items():
        if course.course_code and prefix in course.course_code:
            return clean_name
        if prefix in course.name:
            return clean_name
    return course.course_code or course.name


async def check_once(client: QuercusClient, store: HistoryStore, dry_run: bool = False) -> int:
    """Execute one polling iteration; API failures are reported, never read as "no news"."""
    try:
        alerts = await _poll(client, store, dry_run)
    except QuercusAuthError as exc:
        logger.error(f"Quercus rejected the API token: {exc}")
        if not store.auth_alert_sent and not dry_run:
            sent = await send_telegram_message(
                "🔑 <b>[UofT Quercus Bot] API 토큰이 거부되었습니다</b>\n\n"
                "Quercus 토큰이 만료되었거나 폐기되었습니다. "
                "새 토큰을 발급해 서버의 .env를 갱신해 주세요. 그때까지 알림이 오지 않습니다."
            )
            store.auth_alert_sent = sent
        save_history(store)
        return 0
    except QuercusAPIError as exc:
        logger.error(f"Quercus check failed, will retry next poll: {exc}")
        save_history(store)
        return 0

    store.auth_alert_sent = False
    save_history(store)
    return alerts


async def _poll(client: QuercusClient, store: HistoryStore, dry_run: bool) -> int:
    """Run the checks for all active courses. Raises QuercusAPIError on API failure."""
    now = datetime.now(timezone.utc)
    logger.info(f"Starting Quercus check iteration at {now.isoformat()} (Initialized: {store.initialized})...")
    alerts_dispatched = 0

    # 1. Fetch active courses
    courses = await client.get_active_courses()
    if not courses:
        logger.warning("No active courses returned from Quercus API.")
        return 0

    course_map: dict[int, str] = {c.id: get_clean_course_name(c) for c in courses}
    course_ids = list(course_map.keys())
    logger.info(f"Monitoring {len(courses)} active courses: {', '.join(course_map.values())}")

    # 2. Check Announcements
    announcements = await client.get_announcements(course_ids)
    sent_ann_set = set(store.sent_announcements)

    for ann in announcements:
        if ann.id not in sent_ann_set:
            course_id = int(ann.context_code.replace("course_", "")) if "course_" in ann.context_code else None
            cname = course_map.get(course_id, "U of T Course") if course_id else "U of T Course"

            if store.initialized and not dry_run:
                msg = format_announcement_message(cname, ann)
                if not await send_telegram_message(msg):
                    continue  # leave unmarked so the next poll retries
                alerts_dispatched += 1
            else:
                logger.info(f"[Initial Sync/DryRun] Cached announcement: {ann.title}")

            sent_ann_set.add(ann.id)

    store.sent_announcements = list(sent_ann_set)

    # 3. Check Assignments, Grades, and Deadlines
    for cid, cname in course_map.items():
        assignments = await client.get_assignments(cid)
        for a in assignments:
            a_key = str(a.id)
            sub = a.submission

            # 3A. Check for new grades
            if sub and sub.score is not None:
                last_score = store.sent_grades.get(a_key)
                if last_score is None:
                    # New grade recorded
                    if store.initialized and not dry_run:
                        msg = format_grade_message(cname, a, sub.score)
                        if not await send_telegram_message(msg):
                            continue  # retry next poll
                        alerts_dispatched += 1
                    else:
                        logger.info(f"[Initial Sync/DryRun] Cached grade: {a.name} -> {sub.score}")
                    store.sent_grades[a_key] = sub.score

            # 3B. Check for approaching deadlines if still unsubmitted
            if a.due_at and (not sub or sub.workflow_state == "unsubmitted"):
                hours_left = (a.due_at - now).total_seconds() / 3600.0
                past_alerts = store.sent_due_alerts.setdefault(a_key, [])

                # Determine alert threshold
                alert_type: Optional[str] = None
                if 48.0 <= hours_left <= 72.0 and "D-3" not in past_alerts:
                    alert_type = "D-3"
                elif 18.0 <= hours_left <= 26.0 and "D-1" not in past_alerts:
                    alert_type = "D-1"
                elif 6.0 <= hours_left <= 13.0 and "D-Day (12시간 전)" not in past_alerts:
                    alert_type = "D-Day (12시간 전)"
                elif 0.0 < hours_left <= 3.5 and "D-Day (마감 직전)" not in past_alerts:
                    alert_type = "D-Day (마감 직전)"

                if alert_type and store.initialized and not dry_run:
                    msg = format_deadline_message(cname, a, alert_type, hours_left)
                    success = await send_telegram_message(msg)
                    if success:
                        alerts_dispatched += 1
                        past_alerts.append(alert_type)

        # 4. Check for New Course Files
        files = await client.get_course_files(cid)
        sent_files_set = set(store.sent_files)
        for f in files:
            if f.id not in sent_files_set:
                if store.initialized and not dry_run:
                    msg = format_new_file_message(cname, f)
                    if not await send_telegram_message(msg):
                        continue  # retry next poll
                    alerts_dispatched += 1
                else:
                    logger.info(f"[Initial Sync/DryRun] Cached file: {f.display_name}")
                sent_files_set.add(f.id)
        store.sent_files = list(sent_files_set)

    # Finalize state
    if not store.initialized:
        store.initialized = True
        logger.info("Initial sync complete. All past announcements, grades, and files have been indexed.")

    store.last_check_at = now
    logger.info(f"Check iteration completed. Total alerts sent: {alerts_dispatched}")
    return alerts_dispatched


async def run_daemon() -> None:
    """Run persistent monitoring daemon with configured poll interval."""
    interval = int(os.getenv("POLL_INTERVAL_SECONDS", "1800"))
    client = QuercusClient()
    store = load_history()

    logger.info(f"Starting Quercus Telegram Bot Daemon (Poll Interval: {interval}s)...")
    await send_telegram_message(
        f"🤖 <b>[UofT Quercus Bot] 데몬 가동 시작</b>\n\n"
        f"• 모니터링 주기: {interval // 60}분\n"
        f"• 상태: 4개 수강 과목 실시간 감시 활성화"
    )

    try:
        while True:
            try:
                await check_once(client, store)
            except Exception as exc:
                logger.error(f"Error during check iteration: {exc}", exc_info=True)

            logger.info(f"Sleeping for {interval} seconds until next check...")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("Daemon received cancellation signal. Shutting down gracefully...")
