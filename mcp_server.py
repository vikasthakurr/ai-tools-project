"""
MCP Server for Text-to-SQL Database Access
==========================================

A Model Context Protocol (MCP) server that provides secure, read-only
access to the e-commerce SQLite database. Exposes tools for schema
discovery, query validation, and query execution.

Features:
- Read-only SQLite access (database opened in ?mode=ro)
- Schema discovery (tables, columns, relationships)
- SQL validation (SELECT-only, blocked keywords)
- Query execution with row limits
- Structured logging

Usage:
    python mcp_server.py

MCP Configuration (add to .kiro/settings/mcp.json or equivalent):
    {
        "mcpServers": {
            "text-to-sql-db": {
                "command": "python",
                "args": ["mcp_server.py"],
                "env": {
                    "DATABASE_PATH": "./ecommerce.db"
                }
            }
        }
    }
"""

import os
import re
import sys
import json
import sqlite3
import logging
from typing import Any
from datetime import datetime

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,  # MCP uses stdout for protocol, logs go to stderr
)
logger = logging.getLogger("mcp-db-server")

# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ecommerce.db")
MAX_ROWS = 100
MAX_QUERY_LENGTH = 2000

BLOCKED_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "GRANT", "REVOKE",
]

# ============================================================
# DATABASE CONNECTION
# ============================================================


class DatabaseManager:
    """Manages read-only SQLite database connection."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None

    def connect(self):
        """Open read-only connection."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        uri = f"file:{self.db_path}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path} (read-only)")

    def disconnect(self):
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self.connect()
        return self._conn

    def get_tables(self) -> list[dict]:
        """Get all table names."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [{"name": row[0]} for row in cursor.fetchall()]

    def get_table_schema(self, table_name: str) -> dict:
        """Get detailed schema for a specific table."""
        # Validate table name (prevent SQL injection in PRAGMA)
        tables = [t["name"] for t in self.get_tables()]
        if table_name not in tables:
            raise ValueError(f"Table '{table_name}' does not exist")

        columns = []
        cursor = self.conn.execute(f"PRAGMA table_info({table_name})")
        for col in cursor.fetchall():
            columns.append({
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": bool(col[3]),
                "default_value": col[4],
                "primary_key": bool(col[5]),
            })

        # Get foreign keys
        fk_cursor = self.conn.execute(f"PRAGMA foreign_key_list({table_name})")
        foreign_keys = []
        for fk in fk_cursor.fetchall():
            foreign_keys.append({
                "from_column": fk[3],
                "to_table": fk[2],
                "to_column": fk[4],
            })

        # Get row count
        count_cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = count_cursor.fetchone()[0]

        return {
            "name": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys,
            "row_count": row_count,
        }

    def get_full_schema(self) -> list[dict]:
        """Get schema for all tables."""
        tables = self.get_tables()
        return [self.get_table_schema(t["name"]) for t in tables]

    def get_schema_string(self) -> str:
        """Get schema as a human-readable string."""
        parts = []
        for table in self.get_full_schema():
            cols = []
            for c in table["columns"]:
                pk = " PK" if c["primary_key"] else ""
                nn = " NOT NULL" if c["notnull"] else ""
                cols.append(f"    {c['name']} ({c['type']}{pk}{nn})")
            col_str = "\n".join(cols)

            fk_str = ""
            if table["foreign_keys"]:
                fks = [f"    FK: {fk['from_column']} → {fk['to_table']}.{fk['to_column']}"
                       for fk in table["foreign_keys"]]
                fk_str = "\n" + "\n".join(fks)

            parts.append(f"TABLE: {table['name']} ({table['row_count']} rows)\n{col_str}{fk_str}")

        return "\n\n".join(parts)

    def execute_query(self, sql: str) -> dict:
        """Execute a validated SQL query and return results."""
        cursor = self.conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(row) for row in cursor.fetchmany(MAX_ROWS)]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) == MAX_ROWS,
        }


# ============================================================
# SQL VALIDATOR
# ============================================================


class SQLValidator:
    """Validates SQL queries for safety before execution."""

    @staticmethod
    def validate(sql: str) -> tuple[bool, str]:
        """
        Validate SQL query. Returns (is_valid, error_message).
        """
        if not sql or not sql.strip():
            return False, "Empty query."

        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()

        # Must start with SELECT or WITH
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            return False, "Only SELECT queries are allowed."

        # Check blocked keywords
        for keyword in BLOCKED_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, sql_upper):
                return False, f"Blocked keyword detected: {keyword}. Only read operations are permitted."

        # Length check
        if len(sql_clean) > MAX_QUERY_LENGTH:
            return False, f"Query too long ({len(sql_clean)} chars). Maximum is {MAX_QUERY_LENGTH}."

        # No multiple statements
        sql_no_trailing = sql_clean.rstrip(";")
        if ";" in sql_no_trailing:
            return False, "Multiple statements are not allowed."

        return True, ""


# ============================================================
# MCP PROTOCOL IMPLEMENTATION
# ============================================================


class MCPServer:
    """
    Model Context Protocol server for database access.

    Implements the MCP stdio transport protocol:
    - Reads JSON-RPC messages from stdin
    - Writes JSON-RPC responses to stdout
    - Logs to stderr
    """

    def __init__(self):
        self.db = DatabaseManager(DATABASE_PATH)
        self.validator = SQLValidator()
        self._request_count = 0

    def run(self):
        """Main event loop — read stdin, process, write stdout."""
        logger.info("MCP Server starting...")
        self.db.connect()
        logger.info("MCP Server ready. Waiting for messages on stdin.")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                message = json.loads(line)
                response = self._handle_message(message)
                if response is not None:
                    self._send_response(response)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                self._send_error(-32700, "Parse error", None)
            except Exception as e:
                logger.error(f"Unhandled error: {e}")
                msg_id = message.get("id") if isinstance(message, dict) else None
                self._send_error(-32603, str(e), msg_id)

    def _handle_message(self, message: dict) -> dict | None:
        """Route incoming JSON-RPC message to handler."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        self._request_count += 1
        logger.info(f"[{self._request_count}] Method: {method}")

        # Protocol methods
        handlers = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "ping": self._handle_ping,
        }

        handler = handlers.get(method)
        if handler:
            result = handler(params)
            if msg_id is not None:
                return {"jsonrpc": "2.0", "id": msg_id, "result": result}
            return None  # Notification — no response needed
        else:
            logger.warning(f"Unknown method: {method}")
            if msg_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            return None

    def _send_response(self, response: dict):
        """Write JSON-RPC response to stdout."""
        output = json.dumps(response)
        sys.stdout.write(output + "\n")
        sys.stdout.flush()

    def _send_error(self, code: int, message: str, msg_id):
        """Send JSON-RPC error response."""
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": code, "message": message},
        }
        self._send_response(response)

    # ========================================================
    # PROTOCOL HANDLERS
    # ========================================================

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": "text-to-sql-db",
                "version": "1.0.0",
            },
        }

    def _handle_initialized(self, params: dict) -> dict:
        """Handle initialized notification."""
        logger.info("Client initialized successfully")
        return {}

    def _handle_ping(self, params: dict) -> dict:
        """Handle ping request."""
        return {}

    # ========================================================
    # TOOLS
    # ========================================================

    def _handle_tools_list(self, params: dict) -> dict:
        """Return available tools."""
        return {
            "tools": [
                {
                    "name": "list_tables",
                    "description": "List all tables in the e-commerce database with their row counts.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
                {
                    "name": "describe_table",
                    "description": "Get detailed schema for a specific table including columns, types, primary keys, and foreign keys.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Name of the table to describe (e.g., 'customers', 'orders', 'products')",
                            },
                        },
                        "required": ["table_name"],
                    },
                },
                {
                    "name": "get_full_schema",
                    "description": "Get the complete database schema as a formatted string showing all tables, columns, types, and relationships. Useful for building SQL queries.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
                {
                    "name": "validate_sql",
                    "description": "Validate a SQL query for safety without executing it. Checks that the query is SELECT-only and contains no destructive operations.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "The SQL query to validate",
                            },
                        },
                        "required": ["sql"],
                    },
                },
                {
                    "name": "execute_query",
                    "description": "Execute a read-only SQL SELECT query against the e-commerce database. Returns up to 100 rows. The query is validated for safety before execution.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "A valid SQL SELECT query to execute",
                            },
                        },
                        "required": ["sql"],
                    },
                },
                {
                    "name": "get_sample_data",
                    "description": "Get a sample of rows from a specific table. Useful for understanding the data format and content.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Name of the table to sample",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Number of rows to return (default: 5, max: 20)",
                                "default": 5,
                            },
                        },
                        "required": ["table_name"],
                    },
                },
            ],
        }

    def _handle_tools_call(self, params: dict) -> dict:
        """Execute a tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.info(f"Tool call: {tool_name} args={json.dumps(arguments)[:200]}")

        tool_handlers = {
            "list_tables": self._tool_list_tables,
            "describe_table": self._tool_describe_table,
            "get_full_schema": self._tool_get_full_schema,
            "validate_sql": self._tool_validate_sql,
            "execute_query": self._tool_execute_query,
            "get_sample_data": self._tool_get_sample_data,
        }

        handler = tool_handlers.get(tool_name)
        if not handler:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }

        try:
            result = handler(arguments)
            return {"content": [{"type": "text", "text": result}], "isError": False}
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}

    def _tool_list_tables(self, args: dict) -> str:
        """List all tables with row counts."""
        tables = self.db.get_full_schema()
        lines = ["DATABASE TABLES:", "=" * 40]
        for t in tables:
            col_count = len(t["columns"])
            lines.append(f"  {t['name']:<15} | {t['row_count']:>6} rows | {col_count} columns")
        lines.append(f"\nTotal: {len(tables)} tables")
        return "\n".join(lines)

    def _tool_describe_table(self, args: dict) -> str:
        """Describe a specific table."""
        table_name = args.get("table_name", "")
        if not table_name:
            return "Error: table_name is required"

        try:
            schema = self.db.get_table_schema(table_name)
        except ValueError as e:
            return str(e)

        lines = [f"TABLE: {schema['name']} ({schema['row_count']} rows)", "=" * 50]
        lines.append(f"\n{'Column':<20} {'Type':<10} {'Nullable':<10} {'PK':<5}")
        lines.append("-" * 50)
        for col in schema["columns"]:
            nullable = "NO" if col["notnull"] else "YES"
            pk = "YES" if col["primary_key"] else ""
            lines.append(f"  {col['name']:<18} {col['type']:<10} {nullable:<10} {pk:<5}")

        if schema["foreign_keys"]:
            lines.append(f"\nFOREIGN KEYS:")
            for fk in schema["foreign_keys"]:
                lines.append(f"  {fk['from_column']} → {fk['to_table']}.{fk['to_column']}")

        return "\n".join(lines)

    def _tool_get_full_schema(self, args: dict) -> str:
        """Get complete schema string."""
        return self.db.get_schema_string()

    def _tool_validate_sql(self, args: dict) -> str:
        """Validate SQL without executing."""
        sql = args.get("sql", "")
        if not sql:
            return "Error: sql parameter is required"

        is_valid, error = self.validator.validate(sql)
        if is_valid:
            return f"✓ VALID: Query passes all safety checks.\n\nQuery: {sql}"
        else:
            return f"✗ INVALID: {error}\n\nQuery: {sql}"

    def _tool_execute_query(self, args: dict) -> str:
        """Execute a validated SQL query."""
        sql = args.get("sql", "")
        if not sql:
            return "Error: sql parameter is required"

        # Validate first
        is_valid, error = self.validator.validate(sql)
        if not is_valid:
            return f"BLOCKED: {error}\n\nQuery: {sql}"

        # Execute
        try:
            result = self.db.execute_query(sql)
            lines = [f"Query executed successfully."]
            lines.append(f"Rows returned: {result['row_count']}")
            if result["truncated"]:
                lines.append(f"(Results truncated to {MAX_ROWS} rows)")
            lines.append(f"\nColumns: {', '.join(result['columns'])}")
            lines.append("")

            # Format results as text table
            if result["rows"]:
                # Header
                lines.append(" | ".join(str(c) for c in result["columns"]))
                lines.append("-" * 60)
                # Rows
                for row in result["rows"]:
                    values = [str(row.get(c, "NULL")) for c in result["columns"]]
                    lines.append(" | ".join(values))
            else:
                lines.append("(No rows returned)")

            return "\n".join(lines)
        except sqlite3.Error as e:
            return f"SQL Execution Error: {str(e)}\n\nQuery: {sql}"

    def _tool_get_sample_data(self, args: dict) -> str:
        """Get sample rows from a table."""
        table_name = args.get("table_name", "")
        limit = min(args.get("limit", 5), 20)  # Cap at 20

        if not table_name:
            return "Error: table_name is required"

        # Validate table exists
        tables = [t["name"] for t in self.db.get_tables()]
        if table_name not in tables:
            return f"Error: Table '{table_name}' does not exist. Available: {', '.join(tables)}"

        sql = f"SELECT * FROM {table_name} LIMIT {limit}"
        result = self.db.execute_query(sql)

        lines = [f"SAMPLE DATA: {table_name} (showing {result['row_count']} rows)", "=" * 60]
        if result["rows"]:
            lines.append(" | ".join(result["columns"]))
            lines.append("-" * 60)
            for row in result["rows"]:
                values = [str(row.get(c, "NULL"))[:30] for c in result["columns"]]
                lines.append(" | ".join(values))
        return "\n".join(lines)

    # ========================================================
    # RESOURCES
    # ========================================================

    def _handle_resources_list(self, params: dict) -> dict:
        """Return available resources."""
        return {
            "resources": [
                {
                    "uri": "db://schema",
                    "name": "Database Schema",
                    "description": "Complete database schema with all tables, columns, types, and relationships",
                    "mimeType": "text/plain",
                },
                {
                    "uri": "db://tables",
                    "name": "Table List",
                    "description": "List of all tables in the database",
                    "mimeType": "application/json",
                },
                {
                    "uri": "db://relationships",
                    "name": "Table Relationships",
                    "description": "Foreign key relationships between tables",
                    "mimeType": "text/plain",
                },
            ],
        }

    def _handle_resources_read(self, params: dict) -> dict:
        """Read a resource by URI."""
        uri = params.get("uri", "")

        if uri == "db://schema":
            content = self.db.get_schema_string()
        elif uri == "db://tables":
            tables = self.db.get_full_schema()
            content = json.dumps(tables, indent=2)
        elif uri == "db://relationships":
            content = self._get_relationships_string()
        else:
            return {
                "contents": [{"uri": uri, "text": f"Unknown resource: {uri}", "mimeType": "text/plain"}]
            }

        return {
            "contents": [{"uri": uri, "text": content, "mimeType": "text/plain"}]
        }

    def _get_relationships_string(self) -> str:
        """Build a human-readable relationships string."""
        lines = ["DATABASE RELATIONSHIPS", "=" * 50, ""]
        for table in self.db.get_full_schema():
            if table["foreign_keys"]:
                for fk in table["foreign_keys"]:
                    lines.append(
                        f"  {table['name']}.{fk['from_column']} → {fk['to_table']}.{fk['to_column']}"
                    )
        lines.append("")
        lines.append("JOIN PATHS:")
        lines.append("  customers → orders → order_items → products → categories")
        lines.append("  orders → payments")
        lines.append("  orders → employees")
        lines.append("  employees → employees (self-join via manager_id)")
        return "\n".join(lines)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    server = MCPServer()
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        server.db.disconnect()
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
        sys.exit(1)
