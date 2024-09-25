from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.db import get_session, create_tables
from model import Product, ProductUpdate
from sqlmodel import Session
import json

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    print('Creating Tables...')
    create_tables()
    print("Tables Created...")
    yield

app = FastAPI(lifespan=lifespan, title="Product Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8009",
            "description": "Development Server"
        }
    ]
)

# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

@app.post("/product", response_model=Product)
async def create_product(
    product: Product, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    db_product = Product(**product.dict(exclude_unset=True))
    session.add(db_product)
    session.commit()
    session.refresh(db_product)

    product_dict = db_product.dict()
    product_json = json.dumps(product_dict).encode("utf-8")
    
    await producer.send_and_wait("product_topic", product_json)

    return db_product

@app.put("/product/{product_id}", response_model=Product)
async def update_product(
    product_id: int, 
    product: ProductUpdate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    db_product = session.get(Product, product_id)
    
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in product.dict().items():
        setattr(db_product, field, value)
    session.commit()
    session.refresh(db_product)
    
    product_dict = db_product.dict()
    product_json = json.dumps(product_dict).encode("utf-8")
    
    await producer.send_and_wait("product_topic", product_json)

    return db_product
