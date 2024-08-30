from typing import Optional
from sqlmodel import SQLModel, Field
from sqlmodel import Relationship, SQLModel

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str = Field(min_length=3, max_length=100)
    quantity: int = Field(default=0)
    price: int
    
    
class ProductUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    quantity: int = Field(default=0)
    price: int | None = None
   
