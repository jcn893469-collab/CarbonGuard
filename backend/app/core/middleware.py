"""Small ASGI protections for API responses and JSON request bodies."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BODY_BYTES = 1_048_576
_SECURITY_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
)


class SecurityHeadersAndBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = MAX_REQUEST_BODY_BYTES,
    ) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        api_response = scope.get("path", "").startswith("/api/")
        if scope["type"] != "http":
            await self.app(scope, receive, self._secure_send(send))
            return

        secure_send = self._secure_send(send, cache_api=api_response)
        content_length = next(
            (
                value
                for name, value in scope.get("headers", [])
                if name.lower() == b"content-length"
            ),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_size:
                    await self._reject_large_body(scope, receive, secure_send)
                    return
            except ValueError:
                pass

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_size:
                await self._reject_large_body(scope, receive, secure_send)
                return
            if not message.get("more_body", False):
                break

        request_body = bytes(body)
        body_sent = False

        async def replay_body() -> Message:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {
                    "type": "http.request",
                    "body": request_body,
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, replay_body, secure_send)

    def _secure_send(self, send: Send, *, cache_api: bool = False) -> Send:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                headers.extend(
                    (name, value)
                    for name, value in _SECURITY_HEADERS
                    if name not in existing
                )
                if cache_api and b"cache-control" not in existing:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        return send_with_headers

    async def _reject_large_body(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "detail": (
                    f"Request body must not exceed {self.max_body_size} bytes"
                )
            },
        )
        await response(scope, receive, send)
