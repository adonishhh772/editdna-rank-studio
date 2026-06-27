from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.constants.security_headers import SECURITY_RESPONSE_HEADERS


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        for header_name, header_value in SECURITY_RESPONSE_HEADERS.items():
            response.headers[header_name] = header_value
        return response
