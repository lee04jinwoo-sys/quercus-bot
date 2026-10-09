"""Telegram notification sender module."""

import html
import logging
import os
import re
from typing import Optional
import httpx
from dotenv import load_dotenv

from quercus_bot.models import Announcement, Assignment, CourseFile

load_dotenv()

logger = logging.getLogger("quercus_bot.notifier")


def clean_html(raw_html: str) -> str:
    """Strip HTML tags and convert entities for clean Telegram messaging."""
    clean_text = re.sub(r"<br\s*/?>", "\n", raw_html)
    clean_text = re.sub(r"</p>", "\n", clean_text)
    clean_text = re.sub(r"<[^>]+>", "", clean_text)
    clean_text = html.unescape(clean_text)
    return clean_text.strip()


async def send_telegram_message(
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """Send an asynchronous message to the configured Telegram chat."""
    token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Telegram notification sent successfully.")
            return True
    except httpx.HTTPError as exc:
        logger.error(f"Failed to send Telegram message: {exc}")
        return False


def format_announcement_message(course_name: str, ann: Announcement) -> str:
    """Format a new announcement alert."""
    cleaned_msg = clean_html(ann.message)
    # Truncate if body is too long for Telegram
    if len(cleaned_msg) > 500:
        cleaned_msg = cleaned_msg[:497] + "..."

    return (
        f"📢 <b>[UofT Quercus] 새 공지사항</b>\n\n"
        f"📚 <b>과목:</b> {html.escape(course_name)}\n"
        f"📌 <b>제목:</b> {html.escape(ann.title)}\n"
        f"🕒 <b>게시:</b> {ann.posted_at.strftime('%m/%d %H:%M')}\n\n"
        f"<b>[내용 요약]</b>\n"
        f"{html.escape(cleaned_msg)}"
    )


def format_deadline_message(
    course_name: str, assignment: Assignment, alert_type: str, hours_left: float
) -> str:
    """Format a pending assignment deadline reminder."""
    due_str = assignment.due_at.strftime("%m/%d(%a) %H:%M") if assignment.due_at else "미정"
    pts = f" ({assignment.points_possible}점)" if assignment.points_possible else ""

    return (
        f"⏰ <b>[UofT Quercus] 과제 마감 임박 ({alert_type})</b>\n\n"
        f"📚 <b>과목:</b> {html.escape(course_name)}\n"
        f"📝 <b>과제명:</b> {html.escape(assignment.name)}{pts}\n"
        f"⏳ <b>마감 시각:</b> {due_str} (약 {int(hours_left)}시간 남음)\n"
        f"⚠️ <b>상태:</b> 아직 미제출 상태입니다! 늦지 않게 업로드하세요."
    )


def format_grade_message(
    course_name: str, assignment: Assignment, score: float
) -> str:
    """Format a newly published grade alert."""
    total_pts = f" / {assignment.points_possible}점" if assignment.points_possible else ""
    return (
        f"🎉 <b>[UofT Quercus] 성적 채점 완료!</b>\n\n"
        f"📚 <b>과목:</b> {html.escape(course_name)}\n"
        f"📝 <b>항목:</b> {html.escape(assignment.name)}\n"
        f"📊 <b>점수:</b> <b>{score}{total_pts}</b>\n\n"
        f"Quercus에서 피드백과 세부 감점 내역을 확인하세요."
    )


def format_new_file_message(course_name: str, file: CourseFile) -> str:
    """Format a new file upload alert."""
    size_mb = f"{file.size / (1024 * 1024):.1f} MB" if file.size else "정보 없음"
    return (
        f"📁 <b>[UofT Quercus] 새 수업 자료 등록</b>\n\n"
        f"📚 <b>과목:</b> {html.escape(course_name)}\n"
        f"📄 <b>파일명:</b> {html.escape(file.display_name)}\n"
        f"💾 <b>크기:</b> {size_mb}\n"
        f"🕒 <b>업로드:</b> {file.updated_at.strftime('%m/%d %H:%M')}"
    )
