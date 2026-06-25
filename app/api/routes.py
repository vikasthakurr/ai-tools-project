"""
API route definitions — all endpoints for the Text-to-SQL application.
"""
from fastapi import APIRouter, Depends
from app.models.schemas import (
    QueryRequest,
    QueryResponse,
    SchemaResponse,
    HealthResponse,
    HistoryResponse,
    HistoryEntry,
    TableInfo,
    TableColumn,
)
from app.services.ai_service import ai_service
from app.services.database_service import db_service
from app.services.validator_service import validator_service
from app.services.history_service import history_service
from app.api.dependencies import check_rate_limit
from app.config import settings
from app.utils.logger import logger

router = APIRouter()


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
async def query(request: QueryRequest):
    """
    Convert natural language question to SQL and execute.

    Flow: Question → AI → Validate SQL → Execute → Return Results
    """
    question = request.question.strip()
    logger.info(f"Query received: {question}")

    # Step 1: Generate SQL via Gemini
    result = ai_service.generate_sql(question)

    # Handle AI errors
    if result["error"]:
        history_service.add_entry(question=question, success=False, error=result["error"])
        return QueryResponse(
            success=False,
            question=question,
            error=result["error"],
        )

    # Handle CANNOT_ANSWER
    if result["cannot_answer"]:
        error_msg = "This question cannot be answered with the available data. Try asking about customers, orders, products, employees, or payments."
        history_service.add_entry(question=question, success=False, error=error_msg)
        return QueryResponse(
            success=False,
            question=question,
            error=error_msg,
        )

    sql = result["sql"]

    # Step 2: Validate SQL
    is_valid, validation_error = validator_service.validate(sql)
    if not is_valid:
        logger.warning(f"Validation failed: {validation_error}")
        history_service.add_entry(question=question, sql=sql, success=False, error=validation_error)
        return QueryResponse(
            success=False,
            question=question,
            sql=sql,
            error=validation_error,
        )

    # Step 3: Execute SQL
    try:
        rows, columns = db_service.execute_query(sql)
        logger.info(f"Query executed: {len(rows)} rows returned")
        history_service.add_entry(question=question, sql=sql, success=True)
        return QueryResponse(
            success=True,
            question=question,
            sql=sql,
            results=rows,
            columns=columns,
        )
    except Exception as e:
        error_msg = f"Query execution failed: {str(e)}"
        logger.error(f"SQL execution error for query [{sql}]: {e}")
        history_service.add_entry(question=question, sql=sql, success=False, error=str(e))
        return QueryResponse(
            success=False,
            question=question,
            sql=sql,
            error=error_msg,
        )


@router.get("/schema", response_model=SchemaResponse)
async def get_schema():
    """Return database schema (tables, columns, types)."""
    try:
        raw_tables = db_service.get_schema_info()
        tables = [
            TableInfo(
                name=t["name"],
                columns=[TableColumn(name=c["name"], type=c["type"]) for c in t["columns"]],
            )
            for t in raw_tables
        ]
        return SchemaResponse(tables=tables)
    except Exception as e:
        logger.error(f"Schema fetch error: {e}")
        return SchemaResponse(tables=[])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Application health check."""
    db_ok = db_service.is_connected()
    gemini_ok = ai_service.is_configured()

    if db_ok and gemini_ok:
        status = "healthy"
    elif db_ok or gemini_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        database="connected" if db_ok else "disconnected",
        gemini="configured" if gemini_ok else "not configured",
        environment=settings.environment,
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """Return recent query history."""
    entries = history_service.get_history(limit=20)
    history = [
        HistoryEntry(
            id=e["id"],
            question=e["question"],
            sql=e.get("sql"),
            success=e["success"],
            error=e.get("error"),
            timestamp=e["timestamp"],
        )
        for e in entries
    ]
    return HistoryResponse(history=history, total=history_service.get_total())
