from contextlib import asynccontextmanager
import asyncio
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.db.db import create_tables, get_session
from fastapi import Depends, FastAPI, HTTPException
from typing import Annotated, List
from sqlmodel import Session
from app.model.inventory_model import Inventorys, InventoryUpdate

@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables')
    create_tables()
    print("Tables Created")
    # Start Kafka Consumer as a background task
    consumer_task = asyncio.create_task(consume_messages())
    yield
    await consumer_task  # Ensure the consumer task is properly handled on shutdown

app = FastAPI(
    lifespan=lifespan, title="Inventory Page", version='1.0.0'
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
    db_inventory = Inventorys(**inventory.dict())
    session.add(db_inventory)
    session.commit()
    session.refresh(db_inventory)

    # Send Kafka message
    await producer.send_and_wait("inventory_topic", f"Created: {db_inventory.id}".encode('utf-8'))

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
    
    # Send Kafka message
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

# Kafka Consumer
async def consume_messages():
    consumer = AIOKafkaConsumer(
        'inventory_topic',
        bootstrap_servers='broker:19092',
        group_id="inventory-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            print(f"Consumed message: {msg.value.decode('utf-8')}")
    finally:
        await consumer.stop()
