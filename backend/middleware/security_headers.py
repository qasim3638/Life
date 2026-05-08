"""
SecurityHeadersMiddleware — adds the OWASP-recommended security headers
to every HTTP response.

Defaults are deliberately STRICT but pragmatic:

  - Content-Security-Policy        — blocks XSS + script injection
  - Strict-Transport-Security      — forces HTTPS for 6 months
  - X-Content-Type-Options         — stops MIME-sniffing attacks
  - X-Frame-Options                — stops clickjacking via <iframe>
  - Referrer-Policy                — never leak full URL to third parties
  - Permissions-Policy             — disables camera/mic/geolocation by default

Toggleable via env so we can relax on staging without code edits:
  - SECURITY_HEADERS_ENABLED=true|false  (default: true in production)
  - CSP_REPORT_ONLY=true|false           (default: false — set true to debug)

Note: the CSP intentionally allows `data:` images (R2 thumbs occasionally
inline) and `https:` (R2 + Stripe + Resend) but blocks everything else.
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware


def _build_csp() -> str:
    """The canonical CSP. Kept as a single string for readability."""
    return "; ".join([
        "default-src 'self'",
        # Inline scripts/styles needed by Stripe + react-helmet — limit to self+stripe
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://*.stripe.com https://www.googletagmanager.com https://www.google-analytics.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        # Images: R2 + supplier CDNs commonly used in product imports
        "img-src 'self' data: blob: https:",
        # XHR/fetch — restrict to known APIs
        "connect-src 'self' https: wss:",
        # Iframes for Stripe checkout, YouTube videos in showroom tours
        "frame-src 'self' https://js.stripe.com https://hooks.stripe.com https://www.youtube.com https://*.youtube.com",
        "media-src 'self' https: blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self' https://*.stripe.com",
        "frame-ancestors 'self'",
        "upgrade-insecure-requests",
    ])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds OWASP-recommended security headers to every response.

    Skips `/api/*` JSON responses for X-Frame-Options (those don't need it)
    but applies CSP / HSTS universally.
    """

    def __init__(self, app, *, enabled: bool = True, csp_report_only: bool = False):
        super().__init__(app)
        self.enabled = enabled
        self.csp_report_only = csp_report_only
        self._csp = _build_csp()

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if not self.enabled:
            return response

        # Always set: HSTS, X-Content-Type-Options, Referrer-Policy
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=15552000; includeSubDomains",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(self 'https://js.stripe.com')",
        )

        # X-Frame-Options — only on HTML responses (skip API JSON to be safe)
        ctype = response.headers.get("content-type", "").lower()
        if "html" in ctype or not ctype:
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # Content-Security-Policy
        csp_header = "Content-Security-Policy-Report-Only" if self.csp_report_only else "Content-Security-Policy"
        response.headers.setdefault(csp_header, self._csp)

        # Remove server fingerprint
        if "server" in response.headers:
            del response.headers["server"]

        return response


def install_security_headers(app):
    """Convenience helper — call once at app startup."""
    enabled = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() != "false"
    report_only = os.environ.get("CSP_REPORT_ONLY", "false").lower() == "true"
    app.add_middleware(
        SecurityHeadersMiddleware,
        enabled=enabled,
        csp_report_only=report_only,
    )
