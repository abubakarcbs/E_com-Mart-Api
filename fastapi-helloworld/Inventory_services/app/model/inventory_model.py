from typing import Optional
from sqlmodel import SQLModel, Field

class Inventorys(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    description: str = Field(min_length=3,max_length=100)
    amount : int = Field(index=True)
    price: int
 
    
class InventoryUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    amount : int = Field(index=True)
    price: int | None = None
    
   