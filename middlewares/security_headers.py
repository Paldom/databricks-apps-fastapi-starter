from fastapi import Request
from secure import Secure


secure_headers = Secure.with_default_headers()


async def security_headers_middleware(request: Request, call_next):
    """Apply recommended security headers to each response."""
    response = await call_next(request)
    await secure_headers.set_headers_async(response)
    return response
