"""
SQLite database operations — read-only connection, schema extraction, query execution.
"""
import sqlite3
from typing import List, Tuple, Optional
from app.config import settings
from app.utils.logger import logger


class DatabaseService:
    """Manages SQLite database connection and operations."""

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._schema_cache: Optional[str] = None

    def connect(self):
        """Open read-only connection to SQLite database."""
        try:
            uri = f"file:{settings.database_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            logger.info(f"Database connected: {settings.database_path}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database disconnected")

    def is_connected(self) -> bool:
        """Check if database is accessible."""
        try:
            if self._conn is None:
                return False
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def execute_query(self, sql: str) -> Tuple[List[dict], List[str]]:
        """
        Execute a SELECT query and return results.
        Limited to 100 rows maximum.
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = self._conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(row) for row in cursor.fetchmany(100)]
        logger.debug(f"Query returned {len(rows)} rows")
        return rows, columns

    def get_schema_info(self) -> List[dict]:
        """Extract table and column metadata for /api/schema."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        tables = []
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        for row in cursor.fetchall():
            table_name = row[0]
            columns = []
            col_cursor = self._conn.execute(f"PRAGMA table_info({table_name})")
            for col in col_cursor.fetchall():
                columns.append({"name": col[1], "type": col[2]})
            tables.append({"name": table_name, "columns": columns})
        return tables

    def get_schema_string(self) -> str:
        """
        Build schema string for prompt injection.
        Cached after first call for performance.
        """
        if self._schema_cache:
            return self._schema_cache

        schema_parts = []
        for table in self.get_schema_info():
            cols = []
            for c in table["columns"]:
                cols.append(f"{c['name']} ({c['type']})")
            col_str = ", ".join(cols)
            schema_parts.append(f"TABLE: {table['name']}\n  Columns: {col_str}")

        self._schema_cache = "\n\n".join(schema_parts)
        return self._schema_cache


# Singleton
db_service = DatabaseService()
