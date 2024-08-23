from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    name: str
    order_id: int
    amount: float
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentCreate(SQLModel):
    email: str
    name: str
    order_id: int
    amount: float
    status: str
