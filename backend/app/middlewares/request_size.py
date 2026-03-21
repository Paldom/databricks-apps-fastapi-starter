"""Pure ASGI middleware enforcing maximum request body size."""

import json
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


class _BodyTooLargeSignal(Exception):
    """Internal signal — never escapes the middleware."""


class RequestSizeMiddleware:
    """Reject requests whose body exceeds a configurable limit.

    Multipart (file upload) requests use ``max_upload_bytes``; all other
    requests use ``max_bytes``.  The middleware short-circuits on
    ``Content-Length`` when present and also enforces the cap while
    streaming the body.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int = 1_048_576,
        max_upload_bytes: int = 10_485_760,
    ):
        self.app = app
        self.max_bytes = max_bytes
        self.max_upload_bytes = max_upload_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_type = headers.get(b"content-type", b"")
        is_multipart = b"multipart" in content_type
        limit = self.max_upload_bytes if is_multipart else self.max_bytes

        # Fast path: reject based on Content-Length header
        content_length_raw = headers.get(b"content-length")
        if content_length_raw is not None:
            try:
                if int(content_length_raw) > limit:
                    await self._send_413(send, limit)
                    return
            except ValueError:
                pass

        # Slow path: wrap receive to count streamed bytes
        bytes_received = 0

        async def counting_receive() -> Message:
            nonlocal bytes_received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                bytes_received += len(body)
                if bytes_received > limit:
                    raise _BodyTooLargeSignal()
            return message

        try:
            await self.app(scope, counting_receive, send)
        except _BodyTooLargeSignal:
            await self._send_413(send, limit)

    @staticmethod
    async def _send_413(send: Send, limit: int) -> None:
        logger.warning("Request body too large | limit=%d", limit)

        body = json.dumps(
            {
                "detail": "Request body too large",
                "error_code": "request_too_large",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
