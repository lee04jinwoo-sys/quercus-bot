"""State store and persistence management."""

import json
import logging
from pathlib import Path
from typing import Union

from quercus_bot.models import HistoryStore

logger = logging.getLogger("quercus_bot.storage")

DEFAULT_STORE_PATH = Path("sent_history.json")


def load_history(path: Union[str, Path] = DEFAULT_STORE_PATH) -> HistoryStore:
    """Load sent history store from disk, or create a fresh one."""
    file_path = Path(path)
    if not file_path.exists():
        logger.info(f"History file {file_path} not found. Creating a new store.")
        return HistoryStore()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return HistoryStore.model_validate(data)
    except Exception as exc:
        logger.warning(f"Error loading {file_path} ({exc}). Initializing fresh store.")
        return HistoryStore()


def save_history(store: HistoryStore, path: Union[str, Path] = DEFAULT_STORE_PATH) -> None:
    """Save the history store safely to disk."""
    file_path = Path(path)
    temp_path = file_path.with_suffix(".tmp")

    try:
        data = store.model_dump(mode="json")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        temp_path.replace(file_path)
    except Exception as exc:
        logger.error(f"Failed to save history to {file_path}: {exc}")
        if temp_path.exists():
            temp_path.unlink()
