"""
SQL validation — ensure only safe SELECT queries are executed.
"""
import re
from typing import Tuple
from app.utils.logger import logger


class ValidatorService:
    """Validates generated SQL for safety before execution."""

    BLOCKED_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "ATTACH", "DETACH",
        "PRAGMA", "VACUUM", "GRANT", "REVOKE",
    ]

    MAX_QUERY_LENGTH = 2000

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL query for safety.
        Returns (is_valid, error_message).
        """
        if not sql or not sql.strip():
            return False, "Empty query generated."

        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()

        # Check 1: Must start with SELECT or WITH
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            logger.warning(f"Blocked non-SELECT query: {sql_clean[:80]}")
            return False, "Only read queries (SELECT) are supported."

        # Check 2: No blocked keywords (word boundary match)
        for keyword in self.BLOCKED_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_upper):
                logger.warning(f"Blocked keyword '{keyword}' found in query")
                return False, "Only read queries are supported. Data modification is not allowed."

        # Check 3: Query length
        if len(sql_clean) > self.MAX_QUERY_LENGTH:
            return False, "Generated query is too complex. Try a simpler question."

        # Check 4: No multiple statements
        sql_no_trailing = sql_clean.rstrip(";")
        if ";" in sql_no_trailing:
            logger.warning("Multiple statements detected in query")
            return False, "Multiple statements are not allowed."

        return True, ""


# Singleton
validator_service = ValidatorService()
