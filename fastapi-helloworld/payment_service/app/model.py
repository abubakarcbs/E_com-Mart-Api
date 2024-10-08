from typing import Annotated
from pydantic import BaseModel
from sqlmodel import SQLModel, Field
from fastapi import Form
from datetime import datetime
from typing import Optional

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    order_id: int
    status: str
    amount: int  # Add the missing amount field
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentIntentCreate(BaseModel):
    amount: Annotated[
        int, 
        Form(description="Amount in cents (e.g., $10.00 -> 1000 cents)")
    ]  # Amount in cents (e.g., $10.00 -> 1000 cents)
    currency: Annotated[
        str, 
        Form(description="Currency code (e.g., 'usd')")
    ]  # Currency code (e.g., 'usd')
    payment_method_types: Annotated[
        list[str], 
        Form(default=["card"])
    ]  # Defaulting to ["card"]

class PaymentCreate(SQLModel):
    username: Annotated[
        str,
        Form(),
    ]
    order_id: Annotated[
        int,
        Form(),
    ]
    amount: Annotated[
        int,
        Form(),
    ]  # Added the amount field in the request model
    status: Annotated[
        str,
        Form(),
    ]
