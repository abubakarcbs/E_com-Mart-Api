from contextlib import asynccontextmanager
from typing import Annotated, List
from fastapi import FastAPI, HTTPException, Query
from app.db.db import create_tables
from app.db.db import get_session
from sqlalchemy import select
from fastapi import Depends
from sqlmodel import Session
from app.model.order_model import Order, OrderUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables')
    create_tables()
    print("Tables Created")
    yield

app = FastAPI(
    lifespan=lifespan, title="Inventory Page", version='1.0.0'
)

@app.get("/")
def read_root():
    return {"Hello": "from order service"}

@app.post("/order")
def create_order(order: Order, session: Annotated[Session, Depends(get_session)]):
    db_order = Order(**order.dict())  
    session.add(db_order)             
    session.commit()                  
    session.refresh(db_order)         
    return db_order
        
@app.get("/order/{order_id}")
def get_order(order_id: int, session: Annotated[Session, Depends(get_session)]):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.put("/order/{order_id}")
def update_order(order_id: int, order: OrderUpdate, session: Annotated[Session, Depends(get_session)]):
    db_order = session.get(Order, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    for field, value in order.dict().items():
        setattr(db_order, field, value)
    session.commit()
    session.refresh(db_order)
    return db_order



@app.delete("/order/{order_id}")
def delete_order(order_id: int, session: Annotated[Session, Depends(get_session)]):
    order = session.get(Order, order_id)
    session.delete(order)
    session.commit()
    return order

# @app.get("/orders", response_model=List[Order])
# def get_all_orders(session: Annotated[Session, Depends(get_session)], limit: int = 10):
#     orders = session.exec(select(Order).limit(limit)).all()
#     return orders