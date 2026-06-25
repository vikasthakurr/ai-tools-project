"""
AI Service — handles Gemini API calls for text-to-SQL conversion.
Uses the google-genai SDK (new official package).
"""
import time
from typing import Optional
from google import genai
from google.genai import types
from app.config import settings
from app.services.prompt_service import prompt_service
from app.services.database_service import db_service
from app.utils.logger import logger


class AIService:
    """Manages AI-powered text-to-SQL generation via Google Gemini."""

    def __init__(self):
        self._client = None
        self._configured = False

    def configure(self):
        """Initialize Gemini client. Called on app startup."""
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set — AI service disabled")
            return

        try:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            self._configured = True
            logger.info(f"Gemini configured: model={settings.gemini_model}")
        except Exception as e:
            logger.error(f"Gemini configuration failed: {e}")

    def is_configured(self) -> bool:
        """Check if AI service is ready."""
        return self._configured

    def generate_sql(self, question: str) -> dict:
        """
        Convert natural language question to SQL query.

        Returns:
            {
                "sql": str | None,
                "cannot_answer": bool,
                "error": str | None,
                "latency_ms": float,
                "prompt_version": int,
            }
        """
        if not self._configured:
            return {
                "sql": None,
                "cannot_answer": False,
                "error": "AI service not configured. Check GEMINI_API_KEY.",
                "latency_ms": 0,
                "prompt_version": prompt_service.get_version(),
            }

        start_time = time.time()

        # Build prompt
        schema = db_service.get_schema_string()
        system_prompt, user_prompt = prompt_service.build_prompt(question, schema)

        # Call Gemini (with 1 retry)
        generated = None
        last_error = None
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=settings.gemini_model,
                    contents=f"{system_prompt}\n\n{user_prompt}",
                    config=types.GenerateContentConfig(
                        temperature=settings.gemini_temperature,
                        max_output_tokens=settings.gemini_max_tokens,
                    ),
                )
                if response.text:
                    generated = response.text.strip()
                    break
                else:
                    last_error = "Empty response from Gemini"
                    logger.warning(f"Gemini returned empty response on attempt {attempt + 1}")
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {last_error}")
                if attempt == 0:
                    time.sleep(2)  # Pause before retry (avoid rate limits)

        latency_ms = (time.time() - start_time) * 1000

        # Handle API failure
        if generated is None:
            logger.error(f"Gemini API failed after 2 attempts: {last_error}")
            return {
                "sql": None,
                "cannot_answer": False,
                "error": "AI service unavailable. Please try again.",
                "latency_ms": latency_ms,
                "prompt_version": prompt_service.get_version(),
            }

        # Handle CANNOT_ANSWER
        if "CANNOT_ANSWER" in generated:
            logger.info(f"CANNOT_ANSWER for: {question}")
            return {
                "sql": None,
                "cannot_answer": True,
                "error": None,
                "latency_ms": latency_ms,
                "prompt_version": prompt_service.get_version(),
            }

        # Clean response (strip code fences, trailing semicolons)
        sql = self._clean_sql(generated)
        logger.info(f"Generated SQL in {latency_ms:.0f}ms: {sql[:100]}")

        return {
            "sql": sql,
            "cannot_answer": False,
            "error": None,
            "latency_ms": latency_ms,
            "prompt_version": prompt_service.get_version(),
        }

    def _clean_sql(self, raw: str) -> str:
        """Clean up the raw model output to extract SQL."""
        sql = raw.strip()

        # Remove markdown code fences
        if sql.startswith("```"):
            lines = sql.split("\n")
            # Remove first line (```sql or ```)
            lines = lines[1:]
            # Remove last line if it's closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            sql = "\n".join(lines).strip()

        # Remove trailing semicolons (we add them if needed during execution)
        sql = sql.rstrip(";").strip()

        return sql


# Singleton
ai_service = AIService()
