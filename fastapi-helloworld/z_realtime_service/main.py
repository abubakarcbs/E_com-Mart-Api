# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlmodel import Session, SQLModel, select
from app.model.model import SharedCart, ShoppingSession
from typing import List, Dict
import uuid
import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
from contextlib import asynccontextmanager
from app.db.db import engine
import requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(lifespan=lifespan, title="User Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8008",
            "description": "Development Server"
        }
    ]
)

# Dependency
def get_session():
    with Session(engine) as session:
        yield session

# WebSocket Manager to manage active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[uuid.UUID, List[WebSocket]] = {}

    async def connect(self, session_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)

    def disconnect(self, session_id: uuid.UUID, websocket: WebSocket):
        self.active_connections[session_id].remove(websocket)
        if not self.active_connections[session_id]:
            del self.active_connections[session_id]

    async def broadcast(self, session_id: uuid.UUID, message: str):
        for connection in self.active_connections.get(session_id, []):
            await connection.send_text(message)

manager = ConnectionManager()

# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

# Interacting with User and Product Services
USER_SERVICE_URL = "http://user_services:8005"
PRODUCT_SERVICE_URL = "http://Product_services:8002"

async def fetch_user(user_id: int):
    response = requests.get(f"{USER_SERVICE_URL}/users/{user_id}")
    response.raise_for_status()
    return response.json()

async def fetch_product(product_id: int):
    response = requests.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
    response.raise_for_status()
    return response.json()

@app.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: uuid.UUID):
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(session_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)

@app.post("/session/", response_model=ShoppingSession)
async def create_session(users: List[int], session: Session = Depends(get_session)):
    # Validate users via the User Service
    for user_id in users:
        await fetch_user(user_id)
    
    db_session = ShoppingSession(users=users)
    session.add(db_session)
    session.commit()
    session.refresh(db_session)
    return db_session

@app.get("/session/{session_id}/cart", response_model=List[SharedCart])
async def get_shared_cart(session_id: uuid.UUID, session: Session = Depends(get_session)):
    cart_items = session.exec(select(SharedCart).where(SharedCart.session_id == session_id)).all()
    return cart_items

@app.post("/session/{session_id}/cart")
async def add_to_cart(
    session_id: uuid.UUID, user_id: int, product_id: int, quantity: int, 
    session: Session = Depends(get_session), 
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Produce validation messages
    await producer.send_and_wait("user_validation", json.dumps({"user_id": user_id}).encode("utf-8"))
    await producer.send_and_wait("product_validation", json.dumps({"product_id": product_id}).encode("utf-8"))

    # Assuming validation is successful, add to cart
    db_cart_item = SharedCart(session_id=session_id, user_id=user_id, product_id=product_id, quantity=quantity)
    session.add(db_cart_item)
    session.commit()
    session.refresh(db_cart_item)

    # Broadcast to WebSocket clients and produce a Kafka message
    await manager.broadcast(session_id, json.dumps({"action": "add", "item": db_cart_item.dict()}))
    await producer.send_and_wait("cart_updates", json.dumps({"session_id": str(session_id), "user_id": user_id, "product_id": product_id, "quantity": quantity, "action": "add"}).encode("utf-8"))

    return db_cart_item


@app.delete("/session/{session_id}/cart/{cart_item_id}")
async def remove_from_cart(session_id: uuid.UUID, cart_item_id: int, session: Session = Depends(get_session), producer: AIOKafkaProducer = Depends(get_kafka_producer)):
    cart_item = session.get(SharedCart, cart_item_id)
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    session.delete(cart_item)
    session.commit()

    # Broadcast to WebSocket clients
    await manager.broadcast(session_id, json.dumps({"action": "remove", "item_id": cart_item_id}))

    # Produce a Kafka message
    cart_update_msg = json.dumps({
        "session_id": str(session_id),
        "cart_item_id": cart_item_id,
        "action": "remove"
    }).encode("utf-8")
    await producer.send_and_wait("cart_updates", cart_update_msg)

    return {"message": "Item removed from cart"}

# @app.get("/products/", response_model=List[Product])
# async def list_products(session: Session = Depends(get_session)):
#     products = session.exec(select(Product)).all()
#     return products
