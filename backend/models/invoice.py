"""
Pydantic models for Invoices
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum


class InvoiceStatus(str, Enum):
    OPEN_ORDER = "open_order"
    DEPOSIT_ORDER = "deposit_order"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvoiceLineItem(BaseModel):
    product_id: Optional[str] = None  # Optional for manual entries
    product_name: str
    sku: Optional[str] = None
    quantity: float
    m2: Optional[float] = 0
    price: float              # Original/List price
    due_price: Optional[float] = None  # Custom/Negotiated/Due price
    total: Optional[float] = None  # Total for this line item
    discount: float = 0


class DepositEntry(BaseModel):
    date: str
    amount: float
    note: str = ""


class InvoiceCreate(BaseModel):
    invoice_no: str
    date: str
    time: str = ""
    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    customer_address: str = ""
    notes: str = ""
    sales_person: str = ""
    payment_method: str = "Card"
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    deposits: List[DepositEntry] = []
    line_items: List[InvoiceLineItem]
    subtotal: float
    vat: float
    gross_total: float
    total_savings: float = 0
    staff_id: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_no: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None
    sales_person: Optional[str] = None
    payment_method: Optional[str] = None
    showroom_id: Optional[str] = None
    showroom_name: Optional[str] = None
    deposits: Optional[List[DepositEntry]] = None
    line_items: Optional[List[InvoiceLineItem]] = None
    subtotal: Optional[float] = None
    vat: Optional[float] = None
    gross_total: Optional[float] = None
    total_savings: Optional[float] = None
    staff_id: Optional[str] = None


class InvoiceEmailRequest(BaseModel):
    recipient_email: str
    subject: Optional[str] = None
    message: Optional[str] = None
