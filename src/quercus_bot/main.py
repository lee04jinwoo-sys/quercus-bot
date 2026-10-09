"""CLI entrypoint for Quercus Bot."""

import argparse
import asyncio
import sys
from rich.console import Console

from quercus_bot.client import QuercusClient
from quercus_bot.daemon import check_once, run_daemon
from quercus_bot.notifier import send_telegram_message
from quercus_bot.storage import load_history

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="U of T Quercus Telegram Alert Bot")
    parser.add_argument("--once", action="store_true", help="Run a single check iteration and exit")
    parser.add_argument("--dry-run", action="store_true", help="Perform check without dispatching Telegram alerts")
    parser.add_argument("--test-msg", action="store_true", help="Send a test notification to Telegram and exit")
    parser.add_argument("--status", action="store_true", help="Print cached tracking history status")

    args = parser.parse_args()

    if args.test_msg:
        console.print("[bold green]Sending test notification to Telegram...[/bold green]")
        success = asyncio.run(
            send_telegram_message(
                "🧪 <b>[UofT Quercus Bot] 테스트 메시지</b>\n\n"
                "텔레그램 연동이 정상적으로 작동하고 있습니다! 🚀"
            )
        )
        if success:
            console.print("[bold green]Test message sent successfully![/bold green]")
        else:
            console.print("[bold red]Failed to send test message. Check .env credentials.[/bold red]")
            sys.exit(1)
        return

    if args.status:
        store = load_history()
        console.print("[bold cyan]Quercus Bot Sent History Status:[/bold cyan]")
        console.print(f"• Initialized: {store.initialized}")
        console.print(f"• Indexed Announcements: {len(store.sent_announcements)}")
        console.print(f"• Recorded Grades: {len(store.sent_grades)}")
        console.print(f"• Indexed Files: {len(store.sent_files)}")
        console.print(f"• Last Check: {store.last_check_at}")
        return

    if args.once:
        console.print("[bold yellow]Running single check iteration...[/bold yellow]")
        client = QuercusClient()
        store = load_history()
        count = asyncio.run(check_once(client, store, dry_run=args.dry_run))
        console.print(f"[bold green]Single check completed! ({count} alerts dispatched)[/bold green]")
        return

    # Default: Run full daemon
    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        console.print("\n[bold red]Daemon stopped by user.[/bold red]")


if __name__ == "__main__":
    main()
