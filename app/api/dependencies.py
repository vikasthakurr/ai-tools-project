"""
Shared FastAPI dependencies — rate limiting, etc.
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from app.config import settings
from app.utils.logger import logger


# Simple in-memory rate limiter
_request_counts: dict = defaultdict(list)


async def check_rate_limit(request: Request):
    """
    Rate limit middleware — limits requests per IP per minute.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # 1 minute window

    # Clean old entries for this IP
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip] if now - t < window
    ]

    # Clean stale IPs (no requests in last 5 minutes)
    stale_ips = [ip for ip, times in _request_counts.items() if not times]
    for ip in stale_ips:
        del _request_counts[ip]

    # Check limit
    if len(_request_counts[client_ip]) >= settings.rate_limit_per_minute:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again.",
        )

    # Record request
    _request_counts[client_ip].append(now)
