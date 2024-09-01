from typing import Optional
from sqlmodel import SQLModel, Field

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    userid: int
    product_id: int
    product_name: str
    quantity: int
    total_amount: float
    is_paid: bool
    
class OrderUpdate(SQLModel):
    product_id: int = None  # Optional field for updating product information
    product_name: str = None  # Optional field for updating product information
    quantity: int = None
    total_amount: float = None
    is_paid: bool = Field(default=False)
