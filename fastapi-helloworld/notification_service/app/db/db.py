# notification_service/app/models.py

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Notification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    recipient_id: str
    message: str
    notification_type: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
