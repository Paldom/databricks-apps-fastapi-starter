"""OWASP-recommended security headers, tuned for this SPA.

``Secure.with_default_headers()`` (secure >= 2.0) ships a blanket
``script-src 'self'`` CSP that must be tailored for a real app: the frontend
loads Google Fonts and the theme bootstrap, and inline scripts are banned by
design (the theme snippet lives in ``frontend/public/theme-init.js``).
"""

from fastapi import Request
from secure import (
    ContentSecurityPolicy,
    ReferrerPolicy,
    Secure,
    StrictTransportSecurity,
    XContentTypeOptions,
    XFrameOptions,
)

_csp = (
    ContentSecurityPolicy()
    .default_src("'self'")
    .script_src("'self'")
    .style_src("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")
    .font_src("'self'", "data:", "https://fonts.gstatic.com")
    .img_src("'self'", "data:", "blob:")
    .connect_src("'self'")
    .worker_src("'self'", "blob:")
    .object_src("'none'")
    .base_uri("'self'")
)

secure_headers = Secure(
    csp=_csp,
    hsts=StrictTransportSecurity().max_age(31536000).include_subdomains(),
    referrer=ReferrerPolicy().strict_origin_when_cross_origin(),
    xcto=XContentTypeOptions().nosniff(),
    xfo=XFrameOptions().sameorigin(),
)


async def security_headers_middleware(request: Request, call_next):
    """Apply recommended security headers to each response."""
    response = await call_next(request)
    await secure_headers.set_headers_async(response)
    return response
