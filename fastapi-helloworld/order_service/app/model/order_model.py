from sqlmodel import SQLModel, Field

class Order(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    customer_name: str 
    total_amount: float 
    is_paid: bool 
    
class OrderUpdate(SQLModel):
    customer_name: str = None
    total_amount: float = None
    is_paid: bool = None