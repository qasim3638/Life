"""
Utility functions and helpers
"""
import uuid
import random
import string


def generate_id() -> str:
    """Generate a unique ID"""
    return str(uuid.uuid4())


def generate_code(length: int = 8) -> str:
    """Generate a random alphanumeric code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP"""
    return ''.join(random.choices(string.digits, k=length))


def generate_invoice_no(prefix: str = "INV") -> str:
    """Generate an invoice number"""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_suffix}"
