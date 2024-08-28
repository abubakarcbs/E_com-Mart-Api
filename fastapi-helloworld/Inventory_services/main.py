from contextlib import asynccontextmanager
import asyncio
from typing import AsyncGenerator
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.db.db import create_tables, get_session
from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Session
from app.model.inventory_model import Inventorys, InventoryUpdate
import json

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print('Creating Tables...')
    create_tables()
    print("Tables Created")
    # Start Kafka Consumer as a background task
    consumer_task = asyncio.create_task(consume_order_messages())
    yield
    # Ensure the consumer task is properly handled on shutdown
    consumer_task.cancel()
    await consumer_task

app = FastAPI(lifespan=lifespan, title="Inventory Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8001",
            "description": "Development Server"
        }
    ]
)

@app.get("/")
def welcome():
    return {"welcome": "Inventory Page"}

# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

@app.post("/inventory", response_model=Inventorys)
async def create_inventory(
    inventory: InventoryUpdate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    db_inventory = Inventorys(**inventory.dict(exclude_unset=True))
    session.add(db_inventory)
    session.commit()
    session.refresh(db_inventory)

    inventory_dict = {field: getattr(db_inventory, field) for field in db_inventory.__fields__.keys()}
    inventory_json = json.dumps(inventory_dict).encode("utf-8")
    
    await producer.send_and_wait("inventory_topic", inventory_json)

    return db_inventory

@app.put("/inventory/{inventory_id}", response_model=Inventorys)
async def update_inventory(
    inventory_id: int, 
    inventory: InventoryUpdate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    db_inventory = session.get(Inventorys, inventory_id)
    
    if not db_inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    for field, value in inventory.dict().items():
        setattr(db_inventory, field, value)
    session.commit()
    session.refresh(db_inventory)
    
    await producer.send_and_wait("inventory_topic", f"Updated: {db_inventory.id}".encode('utf-8'))

    return db_inventory

@app.get("/inventory/{inventory_id}", response_model=Inventorys)
async def get_inventory(inventory_id: int, session: Session = Depends(get_session)):
    inventory = session.get(Inventorys, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory

@app.delete("/inventory/{inventory_id}", response_model=Inventorys)
async def delete_inventory(inventory_id: int, session: Session = Depends(get_session)):
    inventory = session.get(Inventorys, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    session.delete(inventory)
    session.commit()

    return inventory

# Kafka Consumer for Order Messages
async def consume_order_messages():
    consumer = AIOKafkaConsumer(
        'order_topic',
        bootstrap_servers='broker:19092',
        group_id="inventory-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            order_data = json.loads(msg.value.decode('utf-8'))
            is_available = check_inventory(order_data)
            response = {
                "order_id": order_data['id'],
                "is_available": is_available
            }
            response_json = json.dumps(response).encode('utf-8')
            producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
            await producer.start()
            try:
                await producer.send_and_wait("inventory_response_topic", response_json)
            finally:
                await producer.stop()
    finally:
        await consumer.stop()

def check_inventory(order_data):
    product_id = order_data['product_id']
    required_quantity = order_data['quantity']
    session = next(get_session())
    inventory_item = session.get(Inventorys, product_id)
    return inventory_item.quantity >= required_quantity if inventory_item else False
