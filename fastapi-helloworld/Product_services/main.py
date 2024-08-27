from contextlib import asynccontextmanager
from app.db import create_tables, get_session
from model import ProductUpdate, Products
from sqlalchemy import select
from fastapi import Depends, FastAPI, HTTPException, Query
from typing import  List
from sqlmodel import Session
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
import json
from sqlmodel import create_engine
from sqlmodel import SQLModel, Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables')
    
    print("Tables Created")
    consumer_task = asyncio.create_task(consume_messages())
    create_tables()
    yield
    await consumer_task


app = FastAPI(lifespan=lifespan, title="Hello World API with DB", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8000", # ADD NGROK URL Here Before Creating GPT Action
            "description": "Development Server"
        }
        ]
        )


@app.get("/")
def welcome():
    return {"welcome": "Product Page"}


# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()


@app.post("/products")
async def create_product(
    product: Products, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    db_product = Products(**product.dict(exclude_unset=True))
    session.add(db_product)
    session.commit()
    session.refresh(db_product)

    product_dict = {field: getattr(db_product, field) for field in db_product.__fields__.keys()}
    product_json = json.dumps(product_dict).encode("utf-8")
    
    await producer.send_and_wait("product_topic", product_json)

    return db_product


# update product
@app.put("/products/{product_id}")
async def update_product(
    product_id: int, 
    product_update: ProductUpdate, 
    session: Session = Depends(get_session),
    # producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in product_update.dict().items():
        setattr(product, key, value)
    session.commit()

    product_update_dict = {field: getattr(product, field) for field in product.__fields__.keys()}
    product_update_json = json.dumps(product_update_dict).encode("utf-8")
    
    # await producer.send_and_wait("product_topic", product_update_json)

    return {"message": "Product updated successfully"}


# GET Single Product
@app.get("/products/{product_id}")
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# Delete product
@app.delete("/products/{product_id}")
async def delete_product(
    product_id: int, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()

    delete_message = json.dumps({"product_id": product_id, "action": "deleted"}).encode("utf-8")
    await producer.send_and_wait("product_topic", delete_message)

    return {"message": "Product deleted successfully"}


# Kafka Consumer
async def consume_messages():
    consumer = AIOKafkaConsumer(
        'product_topic',
        bootstrap_servers='broker:19092',
        group_id="product-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            print(f"Consumed message: {msg.value.decode('utf-8')}")
    finally:
        await consumer.stop()
        


        # Create engine
engine = create_engine("sqlite:///database.db", connect_args={"check_same_thread": False})


        # Test route
@app.get("/test")
def test_route():
    SQLModel.metadata.create_all(engine)
    return {"message": "This is a test route"}