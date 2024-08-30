from sqlmodel import SQLModel, Field

class Order(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    customer_name: str = Field(max_length=100)
    product_id: int  # Add this field to reference the product being ordered
    product_name: str = Field(max_length=100)  # Add this field to store the product name
    quantity: int
    total_amount: float
    is_paid: bool = Field(default=False)
    
class OrderUpdate(SQLModel):
    product_id: int = None  # Optional field for updating product information
    product_name: str = None  # Optional field for updating product information
    quantity: int = None
    total_amount: float = None
    is_paid: bool = Field(default=False)
