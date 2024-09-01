from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session
from app.model import Payment, PaymentCreate
from app.db.db import get_session, create_tables, engine
import stripe
from dotenv import load_dotenv
import os
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import asyncio
from contextlib import asynccontextmanager
import logging
from get_email import get_user_email
from get_payment import fetch_order_data, fetch_user_data

# Load environment variables from a .env file
load_dotenv()

# Stripe API keys from environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

stripe.api_key = STRIPE_SECRET_KEY

# Set up logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables...")
    create_tables()
    print("Tables created...")
    # Initialize Kafka Consumer to listen to order_topic
    order_consumer_task = asyncio.create_task(consume_order_messages())
    
    yield
    
    # Ensure the consumer task is properly handled on shutdown
    order_consumer_task.cancel()
    await order_consumer_task
    
# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

app = FastAPI(lifespan=lifespan, title="Payment Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8007",
            "description": "Development Server"
        }
    ]
)

# Dependency to get the database session
def get_session():
    with Session(engine) as session:
        yield session

# Kafka Consumer to listen for order messages
async def consume_order_messages():
    consumer = AIOKafkaConsumer(
        'order_topic',
        bootstrap_servers='broker:19092',
        group_id="payment-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            order_data = json.loads(msg.value.decode('utf-8'))
            logging.info(f"Received order data: {order_data}")
            # Process payment based on order data
            await initiate_payment_process(order_data)
    finally:
        await consumer.stop()

# Function to initiate payment process based on order data
async def initiate_payment_process(order_data):
    session = next(get_session())

    # Fetch user email based on user_id
    user_email = get_user_email(order_data['userid'])

    # Create payment data
    payment_data = PaymentCreate(
        order_id=order_data['id'],
        name=order_data['customer_name'],  # Assuming order data has customer_name
        email=user_email,  # Use the fetched email
        amount=order_data['total_amount'],  # Assuming order data has total_amount
        status='pending'  # Initial status
    )

    # Call the process_payment function with the created payment data
    await process_payment(payment_data, session)

@app.post("/process-payment/")
async def process_payment(
    payment: PaymentCreate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Fetch the order details using the order_id to get the correct total_amount and other details
    order_data = await fetch_order_data(payment.order_id)

    if not order_data:
        raise HTTPException(status_code=404, detail=f"Order with ID '{payment.order_id}' not found.")

    # Fetch the user details using the user_id
    user_data = await fetch_user_data(order_data["userid"])

    if not user_data:
        raise HTTPException(status_code=404, detail=f"User with ID '{order_data['userid']}' not found.")

    # Use the fetched total_amount and user details (name and email)
    total_amount = order_data['total_amount']
    username = user_data['username']
    email = user_data['email']
    
    # Step 1: Create a Stripe Checkout Session
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': username,  # Use fetched username for product name
                    },
                    'unit_amount': int(total_amount * 100),  # Use fetched total_amount
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"http://localhost:8007/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url="http://localhost:8007/cancel",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 2: Save payment details in the database
    db_payment = Payment(
        stripe_checkout_id=checkout_session.id,
        name=username,  # Use fetched username
        email=email,  # Use fetched email
        amount=total_amount,  # Save the fetched total_amount
        status='pending',
        order_id=payment.order_id
    )
    session.add(db_payment)
    session.commit()
    session.refresh(db_payment)

    # Step 3: Produce a Kafka message for payment initiation
    payment_message = json.dumps({
        "event": "payment_initiated",
        "payment_id": db_payment.id,
        "name": db_payment.name,
        "order_id": db_payment.order_id,
        "amount": db_payment.amount,
        "status": db_payment.status,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    await producer.send_and_wait("payment_events", payment_message)

    # Simulate payment confirmation (in reality, you would use a Stripe webhook or polling)
    payment_confirmation = await confirm_payment(checkout_session.id)
    if payment_confirmation:
        db_payment.status = "paid"
        session.commit()
        session.refresh(db_payment)

        # Produce a message to payment_response_topic indicating payment completion
        payment_response_message = json.dumps({
            "event": "payment_confirmed",
            "payment_id": db_payment.id,
            "order_id": db_payment.order_id,
            "status": db_payment.status,
            "timestamp": asyncio.get_event_loop().time()
        }).encode("utf-8")

        await producer.send_and_wait("payment_response_topic", payment_response_message)

    return {"checkout_url": checkout_session.url}

async def confirm_payment(session_id: str):
    # Simulate payment confirmation process
    await asyncio.sleep(5)  # Simulate some delay for payment confirmation
    return True  # In a real application, you would query Stripe or listen to a webhook

@app.get("/payment-details/{order_id}")
async def get_payment_details(order_id: int):
    # Fetch the order details based on order_id
    order_data = await fetch_order_data(order_id)

    if not order_data:
        raise HTTPException(status_code=404, detail=f"Order with ID '{order_id}' not found.")
    
    # Fetch the user details based on user_id from the user service
    user_data = await fetch_user_data(order_data["userid"])  # Only pass user_id

    if not user_data:
        raise HTTPException(status_code=404, detail=f"User with ID '{order_data['userid']}' not found.")
    
    # Prepare the payment details response
    payment_details = {
        "order_id": order_data["id"],
        "username": user_data["username"],  # Using fetched username
        "email": user_data["email"],  # Using fetched email
        "total_amount": order_data["total_amount"]  # Assuming order_data has total_amount
    }
    
    return payment_details
