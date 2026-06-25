"""
Query history service — stores and retrieves past queries in memory.
"""
from typing import List
from datetime import datetime
from app.utils.logger import logger


class HistoryService:
    """Manages in-memory query history."""

    def __init__(self, max_entries: int = 50):
        self._history: List[dict] = []
        self._max_entries = max_entries
        self._counter = 0

    def add_entry(
        self,
        question: str,
        sql: str = None,
        success: bool = True,
        error: str = None,
    ):
        """Add a query to history."""
        self._counter += 1
        entry = {
            "id": self._counter,
            "question": question,
            "sql": sql,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(entry)

        # Trim old entries
        if len(self._history) > self._max_entries:
            self._history = self._history[-self._max_entries:]

        logger.debug(f"History entry #{self._counter}: success={success}")

    def get_history(self, limit: int = 20) -> List[dict]:
        """Get recent query history (newest first)."""
        return list(reversed(self._history[-limit:]))

    def get_total(self) -> int:
        """Get total number of queries processed."""
        return self._counter

    def clear(self):
        """Clear history."""
        self._history = []
        logger.info("History cleared")


# Singleton
history_service = HistoryService()
