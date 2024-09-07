from typing import Optional
from sqlmodel import SQLModel, Field

class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    userid: int
    product_id: int
    product_name: str
    quantity: int
    # New status field
    status: str = Field(default="Pending") 
    
    
class OrderUpdate(SQLModel):
    product_id: int = None  # Optional field for updating product information
    product_name: str = None  # Optional field for updating product information
    quantity: int = None
    # New status field
    status: str = Field(default="Pending") 
    
