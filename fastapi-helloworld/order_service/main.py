from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from app.db.db import create_tables, get_session
from sqlmodel import Session
from app.model.order_model import Order, OrderUpdate
import json
import asyncio
import logging
import httpx


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
    inventory_consumer_task = asyncio.create_task(consume_inventory_response())
    payment_consumer_task = asyncio.create_task(consume_payment_response())
    
    yield
    
    # Ensure the producer is properly stopped
    await app.state.producer.stop()
    
    # Ensure the consumer tasks are properly handled on shutdown
    inventory_consumer_task.cancel()
    payment_consumer_task.cancel()
    await inventory_consumer_task
    await payment_consumer_task


USER_SERVICE_URL = "http://user_services:8005"  # Using service name instead of localhost


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
    # Attempt to save the order to the database
    try:
        db_order = Order(**order.dict())  
        db_order.status = "Pending"  # Set the initial status to "Pending"
        session.add(db_order)             
        session.commit()                  
        session.refresh(db_order)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to save order to the database.")

    # If the order is saved, produce the Kafka messages
    try:
        order_dict = db_order.dict()
        order_json = json.dumps(order_dict).encode("utf-8")

        await producer.send_and_wait("order_topic", order_json)

        order_confirmation_message = json.dumps({
            "event": "order_placed",
            "order_id": db_order.id,
            "order_details": f"Product ID: {db_order.product_id}, Quantity: {db_order.quantity}",
            "timestamp": asyncio.get_event_loop().time()
        }).encode("utf-8")

        await producer.send_and_wait("order_events", order_confirmation_message)
        logging.info(f"Order {db_order.id} created and notification sent via Kafka.")
    except Exception as e:
        logging.error(f"Order {db_order.id} created but failed to send notification via Kafka: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process order notification due to: {str(e)}")

    return db_order


@app.get("/order/{order_id}")
async def get_order(
    order_id: int,
    session: Annotated[Session, Depends(get_session)]
):
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

    order_dict = db_order.dict()
    order_json = json.dumps(order_dict).encode("utf-8")
    
    await producer.send_and_wait("order_topic", order_json)
    
    return db_order


@app.delete("/order/{order_id}")
async def delete_order(
    order_id: int,
    session: Annotated[Session, Depends(get_session)]
):
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    session.delete(order)
    session.commit()
    return order


# Kafka Consumer for Inventory Responses
async def consume_inventory_response():
    consumer = AIOKafkaConsumer(
        'inventory_response_topic',
        bootstrap_servers='broker:19092',
        group_id="order-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            response_data = json.loads(msg.value.decode('utf-8'))
            order_id = response_data['order_id']
            is_available = response_data['is_available']

            session = next(get_session())
            order = session.get(Order, order_id)

            if is_available:
                order.status = "Placed"  # Update status to "Placed"
                logging.info(f"Order {order_id}: Inventory confirmed. Status updated to 'Placed'.")
            else:
                order.status = "Failed"  # Update status to "Failed"
                logging.info(f"Order {order_id}: Inventory not available. Status updated to 'Failed'.")

            session.commit()  # Save the updated status to the database
    finally:
        await consumer.stop()


# Kafka Consumer for Payment Responses
async def consume_payment_response():
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

            session = next(get_session())
            order = session.get(Order, order_id)

            if status == "paid":
                order.status = "Confirmed"  # Update status to "Confirmed"
                logging.info(f"Order {order_id}: Payment confirmed. Status updated to 'Confirmed'.")
            else:
                order.status = "Failed"  # Update status to "Failed"
                logging.info(f"Order {order_id}: Payment failed. Status updated to 'Failed'.")

            session.commit()  # Save the updated status to the database
    finally:
        await consumer.stop()
