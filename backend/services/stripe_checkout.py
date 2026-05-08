"""
Stripe Checkout Helper - Replaces emergentintegrations.payments.stripe.checkout
Standard Stripe SDK implementation for production deployment
"""
import os
import stripe
from typing import List, Optional
from pydantic import BaseModel
from dataclasses import dataclass


class LineItem(BaseModel):
    """Line item for checkout session"""
    name: str
    amount: int  # Amount in cents/pence
    currency: str = "gbp"
    quantity: int = 1
    description: Optional[str] = None
    images: Optional[List[str]] = None


class CheckoutSessionRequest(BaseModel):
    """Request model for creating a checkout session"""
    line_items: List[LineItem]
    success_url: str
    cancel_url: str
    customer_email: Optional[str] = None
    metadata: Optional[dict] = None
    mode: str = "payment"


class CheckoutSessionResponse(BaseModel):
    """Response model for checkout session"""
    session_id: str
    checkout_url: str
    status: str = "created"


class CheckoutStatusResponse(BaseModel):
    """Response model for checkout status"""
    session_id: str
    status: str
    payment_status: str
    customer_email: Optional[str] = None
    amount_total: Optional[int] = None
    currency: Optional[str] = None
    metadata: Optional[dict] = None


class StripeCheckout:
    """Stripe Checkout wrapper class"""
    
    def __init__(self, api_key: str, webhook_url: str = ""):
        self.api_key = api_key
        self.webhook_url = webhook_url
        stripe.api_key = api_key
    
    async def create_checkout_session(self, request: CheckoutSessionRequest) -> CheckoutSessionResponse:
        """Create a Stripe checkout session"""
        try:
            # Build line items for Stripe
            stripe_line_items = []
            for item in request.line_items:
                line_item = {
                    "price_data": {
                        "currency": item.currency,
                        "unit_amount": item.amount,
                        "product_data": {
                            "name": item.name,
                        },
                    },
                    "quantity": item.quantity,
                }
                
                if item.description:
                    line_item["price_data"]["product_data"]["description"] = item.description
                
                if item.images:
                    line_item["price_data"]["product_data"]["images"] = item.images[:8]  # Stripe max 8 images
                
                stripe_line_items.append(line_item)
            
            # Create checkout session
            session_params = {
                "payment_method_types": ["card"],
                "line_items": stripe_line_items,
                "mode": request.mode,
                "success_url": request.success_url,
                "cancel_url": request.cancel_url,
            }
            
            if request.customer_email:
                session_params["customer_email"] = request.customer_email
            
            if request.metadata:
                session_params["metadata"] = request.metadata
            
            session = stripe.checkout.Session.create(**session_params)
            
            return CheckoutSessionResponse(
                session_id=session.id,
                checkout_url=session.url,
                status="created"
            )
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    async def get_checkout_status(self, session_id: str) -> CheckoutStatusResponse:
        """Get the status of a checkout session"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            return CheckoutStatusResponse(
                session_id=session.id,
                status=session.status,
                payment_status=session.payment_status,
                customer_email=session.customer_email,
                amount_total=session.amount_total,
                currency=session.currency,
                metadata=dict(session.metadata) if session.metadata else None
            )
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    async def verify_webhook(self, payload: bytes, signature: str, webhook_secret: str) -> dict:
        """Verify a Stripe webhook signature"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            raise Exception(f"Webhook signature verification failed: {str(e)}")
