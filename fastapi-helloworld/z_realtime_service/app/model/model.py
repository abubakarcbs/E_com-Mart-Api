# models.py
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
import uuid

class SharedCart(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: int  # Placeholder for user_id from User Service
    product_id: int  # Placeholder for product_id from Product Service
    quantity: int

class ShoppingSession(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    users: List[int] = []  # List of user_ids participating in the session
    cart_items: List[SharedCart] = Relationship(back_populates="session")
