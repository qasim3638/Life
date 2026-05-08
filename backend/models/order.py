"""
Pydantic models for Orders
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float


class Order(BaseModel):
    id: str
    customer_email: str
    customer_name: str
    customer_phone: str
    items: List[OrderItem]
    total: float
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderCreate(BaseModel):
    items: List[OrderItem]


class OrderStatusUpdate(BaseModel):
    status: str


class OTPRequest(BaseModel):
    phone: str
    customer_email: str = ""


class OTPVerification(BaseModel):
    phone: str
    otp: str
    items: List[OrderItem]
