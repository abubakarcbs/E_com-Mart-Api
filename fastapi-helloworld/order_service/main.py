from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends, logger
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.db.db import create_tables, get_session
from sqlmodel import Session
from app.model.order_model import Order, OrderUpdate
import json
import asyncio
from notification import send_order_confirmation_email  # Import the notification function
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables...')
    create_tables()
    print("Tables Created...")
    
    # Initialize Kafka Producer
    app.state.producer = AIOKafkaProducer(bootstrap_servers="broker:19092")
    await start_producer(app.state.producer)
    
    # Start Kafka Consumers as background tasks
    inventory_consumer_task = asyncio.create_task(consume_inventory_response(app.state.producer))
    payment_consumer_task = asyncio.create_task(consume_payment_response(app.state.producer))
    
    yield
    
    # Ensure the producer is properly stopped
    await app.state.producer.stop()
    
    # Ensure the consumer tasks are properly handled on shutdown
    inventory_consumer_task.cancel()
    payment_consumer_task.cancel()
    await inventory_consumer_task
    await payment_consumer_task

app = FastAPI(lifespan=lifespan, title="Order Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8003",
            "description": "Development Server"
        }
    ]
)

async def start_producer(producer):
    retries = 5
    while retries > 0:
        try:
            await producer.start()
            return
        except Exception as e:
            logging.error(f"Failed to connect to Kafka broker, retries left: {retries}")
            retries -= 1
            await asyncio.sleep(5)
    raise ConnectionError("Failed to connect to Kafka broker after multiple attempts")

@app.get("/")
def read_root():
    return {"Hello": "from order service"}

@app.post("/order")
async def create_order(
    order: Order, 
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(lambda: app.state.producer)
):
    try:
        db_order = Order(**order.dict())  
        session.add(db_order)             
        session.commit()                  
        session.refresh(db_order)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to save order to the database.")

    try:
        order_dict = db_order.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to serialize order data.")
    
    order_json = json.dumps(order_dict).encode("utf-8")

    try:
        await producer.send_and_wait("order_topic", order_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to publish order to Kafka.")
    
    # Send order confirmation email notification
    try:
        order_details = f"Product ID: {db_order.id}, Quantity: {db_order.quantity}, Total Price: {db_order.total_amount}"
        email_sent = send_order_confirmation_email(
            order_id=db_order.id,
            user_email="customer@example.com",  # Replace with actual user's email
            order_details=order_details
        )
        if not email_sent:
            logger.error(f"Order {db_order.id} created but failed to send notification email.")
    except AttributeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to access order attributes: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to send confirmation email.")

    return db_order

@app.get("/order/{order_id}")
def get_order(order_id: int, session: Annotated[Session, Depends(get_session)]):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.put("/order/{order_id}")
async def update_order(
    order_id: int, 
    order: OrderUpdate, 
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(lambda: app.state.producer)
):
    db_order = session.get(Order, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Order not found")
    for field, value in order.dict().items():
        setattr(db_order, field, value)
    session.commit()
    session.refresh(db_order)

    order_dict = {field: getattr(db_order, field) for field in db_order.__fields__.keys()}
    order_json = json.dumps(order_dict).encode("utf-8")
    
    await producer.send_and_wait("order_topic", order_json)
    
    return db_order

@app.delete("/order/{order_id}")
def delete_order(order_id: int, session: Annotated[Session, Depends(get_session)]):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    session.delete(order)
    session.commit()
    return order

# Kafka Consumer for Inventory Responses
async def consume_inventory_response(producer):
    consumer = AIOKafkaConsumer(
        'inventory_response_topic',
        bootstrap_servers='broker:19092',
        group_id="order-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            response_data = json.loads(msg.value.decode('utf-8'))
            product_name = response_data['product_name']
            is_available = response_data['is_available']
            if is_available:
                print(f"Product {product_name}: Inventory available. Proceed with payment.")
                # Logic to proceed with payment or further processing
            else:
                print(f"Product {product_name}: Inventory not available. Notify user.")
                # Logic to handle inventory not available scenario
    finally:
        await consumer.stop()

# Kafka Consumer for Payment Responses
async def consume_payment_response(producer):
    consumer = AIOKafkaConsumer(
        'payment_response_topic',
        bootstrap_servers='broker:19092',
        group_id="order-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            response_data = json.loads(msg.value.decode('utf-8'))
            order_id = response_data['order_id']
            status = response_data['status']
            if status == "paid":
                print(f"Order {order_id}: Payment confirmed. Order is now confirmed.")
                # Logic to mark order as confirmed
            else:
                print(f"Order {order_id}: Payment not confirmed.")
                # Logic to handle failed payment or further processing
    finally:
        await consumer.stop()
