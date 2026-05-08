"""
Sentry Error Monitoring Configuration
Provides error tracking and performance monitoring.
"""
import os
import logging
from typing import Optional

# Check if Sentry SDK is available
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    sentry_sdk = None

# Configuration
SENTRY_DSN = os.environ.get("SENTRY_DSN")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
RELEASE_VERSION = os.environ.get("RELEASE_VERSION", "1.0.0")

_sentry_initialized = False


def init_sentry():
    """Initialize Sentry error monitoring"""
    global _sentry_initialized
    
    if _sentry_initialized:
        return True
    
    if not SENTRY_AVAILABLE:
        logging.info("Sentry SDK not installed. Run: pip install sentry-sdk")
        return False
    
    if not SENTRY_DSN:
        logging.info("Sentry DSN not configured. Set SENTRY_DSN environment variable to enable error monitoring.")
        return False
    
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=ENVIRONMENT,
            release=f"tile-station@{RELEASE_VERSION}",
            
            # Enable tracing for performance monitoring
            enable_tracing=True,
            traces_sample_rate=0.1,  # Sample 10% of transactions for performance
            profiles_sample_rate=0.1,  # Sample 10% for profiling
            
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR
                ),
            ],
            
            # Before send hook - filter sensitive data
            before_send=before_send_filter,
            
            # Attach stack traces to logs
            attach_stacktrace=True,
            
            # Maximum breadcrumbs
            max_breadcrumbs=50,
            
            # Send default PII (disable in strict environments)
            send_default_pii=False,
        )
        
        _sentry_initialized = True
        logging.info(f"Sentry initialized for environment: {ENVIRONMENT}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize Sentry: {e}")
        return False


def before_send_filter(event, hint):
    """Filter sensitive data before sending to Sentry"""
    # Remove sensitive fields
    sensitive_fields = ['password', 'token', 'api_key', 'secret', 'authorization']
    
    def scrub_dict(d):
        if not isinstance(d, dict):
            return d
        return {
            k: '***FILTERED***' if any(s in k.lower() for s in sensitive_fields) else scrub_dict(v)
            for k, v in d.items()
        }
    
    if 'request' in event and 'data' in event['request']:
        event['request']['data'] = scrub_dict(event['request']['data'])
    
    if 'extra' in event:
        event['extra'] = scrub_dict(event['extra'])
    
    return event


def capture_exception(error: Exception, context: Optional[dict] = None):
    """Capture an exception and send to Sentry"""
    if not _sentry_initialized or not sentry_sdk:
        logging.exception(f"Error (Sentry not available): {error}")
        return None
    
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_extra(key, value)
        
        return sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", context: Optional[dict] = None):
    """Capture a message and send to Sentry"""
    if not _sentry_initialized or not sentry_sdk:
        logging.log(
            getattr(logging, level.upper(), logging.INFO),
            f"Message (Sentry not available): {message}"
        )
        return None
    
    with sentry_sdk.push_scope() as scope:
        if context:
            for key, value in context.items():
                scope.set_extra(key, value)
        
        return sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: str, email: str = None, role: str = None):
    """Set user context for Sentry"""
    if not _sentry_initialized or not sentry_sdk:
        return
    
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "role": role
    })


def clear_user_context():
    """Clear user context"""
    if not _sentry_initialized or not sentry_sdk:
        return
    
    sentry_sdk.set_user(None)


def add_breadcrumb(message: str, category: str = "custom", data: Optional[dict] = None):
    """Add a breadcrumb for debugging"""
    if not _sentry_initialized or not sentry_sdk:
        return
    
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        data=data or {}
    )


def start_transaction(name: str, op: str = "task"):
    """Start a performance transaction"""
    if not _sentry_initialized or not sentry_sdk:
        return None
    
    return sentry_sdk.start_transaction(name=name, op=op)


def get_sentry_status() -> dict:
    """Get Sentry configuration status"""
    return {
        "sdk_available": SENTRY_AVAILABLE,
        "initialized": _sentry_initialized,
        "dsn_configured": bool(SENTRY_DSN),
        "environment": ENVIRONMENT,
        "release": f"tile-station@{RELEASE_VERSION}"
    }


# Context manager for transactions
class SentryTransaction:
    """Context manager for Sentry transactions"""
    
    def __init__(self, name: str, op: str = "task"):
        self.name = name
        self.op = op
        self.transaction = None
    
    def __enter__(self):
        if _sentry_initialized and sentry_sdk:
            self.transaction = sentry_sdk.start_transaction(name=self.name, op=self.op)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            if exc_type:
                self.transaction.set_status("internal_error")
            else:
                self.transaction.set_status("ok")
            self.transaction.finish()
        return False
