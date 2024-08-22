# payment_service/app/models.py

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Payment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    order_id: str
    amount: float
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
