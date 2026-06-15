import asyncio
import time
from collections import defaultdict, deque
from secrets import compare_digest

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from procurement_agent.config import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.limit = settings.rate_limit_requests
        self.window = settings.rate_limit_window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def enforce(self, request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        client = forwarded or (request.client.host if request.client else "unknown")
        now = time.monotonic()
        async with self.lock:
            timestamps = self.requests[client]
            while timestamps and timestamps[0] <= now - self.window:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please retry later.",
                )
            timestamps.append(now)


def verify_access_key(request: Request, settings: Settings) -> None:
    if not settings.api_access_key:
        return
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not compare_digest(token, settings.api_access_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid API access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
