"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ============================================================
# REQUEST MODELS
# ============================================================

class QueryRequest(BaseModel):
    """Request body for POST /api/query."""
    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language question about the database",
        examples=["How many customers do we have?"],
    )


# ============================================================
# RESPONSE MODELS
# ============================================================

class QueryResponse(BaseModel):
    """Response body for POST /api/query."""
    success: bool
    question: str
    sql: Optional[str] = None
    results: Optional[List[dict]] = None
    columns: Optional[List[str]] = None
    error: Optional[str] = None


class TableColumn(BaseModel):
    """Column metadata."""
    name: str
    type: str


class TableInfo(BaseModel):
    """Table schema information."""
    name: str
    columns: List[TableColumn]


class SchemaResponse(BaseModel):
    """Response body for GET /api/schema."""
    tables: List[TableInfo]


class HealthResponse(BaseModel):
    """Response body for GET /api/health."""
    status: str
    database: str
    gemini: str
    environment: str


class HistoryEntry(BaseModel):
    """Single query history entry."""
    id: int
    question: str
    sql: Optional[str] = None
    success: bool
    error: Optional[str] = None
    timestamp: str


class HistoryResponse(BaseModel):
    """Response body for GET /api/history."""
    history: List[HistoryEntry]
    total: int
