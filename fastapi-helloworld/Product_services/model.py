from typing import Optional
from sqlmodel import SQLModel, Field
from sqlmodel import Relationship, SQLModel

class Products(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str = Field(min_length=3,max_length=100)
    price: int
    
class Inventory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id")
    quantity: int = Field(default=0)
    product: Optional[Products] = Relationship(back_populates="inventory")
    
class ProductUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    price: int | None = None
   
