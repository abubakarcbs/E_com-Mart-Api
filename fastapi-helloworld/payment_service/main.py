from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session
from app.model import Payment, PaymentCreate
from app.db.db import get_session, create_tables, engine
import stripe
from dotenv import load_dotenv
import os
from aiokafka import AIOKafkaProducer
import json
import asyncio
from contextlib import asynccontextmanager
import logging
import httpx

# User service URL for fetching user email
USER_SERVICE_URL = "http://user_services:8005"

# Load environment variables from a .env file
load_dotenv()

# Stripe API keys from environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

stripe.api_key = STRIPE_SECRET_KEY

# Set up logging
logging.basicConfig(level=logging.INFO)

# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Creating tables...")
    create_tables()
    logging.info("Tables created...")

    yield

# Kafka Producer dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

# FastAPI app initialization
app = FastAPI(
    lifespan=lifespan, 
    title="Payment Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8007",
            "description": "Development Server"
        }
    ]
)

# Function to fetch user email using username
async def get_user_email(username: str):
    async with httpx.AsyncClient() as client:
        try:
            # Sending a request to the user service to fetch user data (email and name)
            response = await client.get(f"{USER_SERVICE_URL}/users/email/{username}")
            response.raise_for_status()  # Raise exception if the request was unsuccessful
            user_data = response.json()  # Parse the response JSON
            return user_data['email'], user_data['name']  # Return email and name
        except httpx.HTTPStatusError as e:
            logging.error(f"Failed to fetch user email: {e}")
            raise HTTPException(status_code=404, detail=f"User with username '{username}' not found")

@app.post("/process-payment/")
async def process_payment(
    payment: PaymentCreate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Fetch user email based on username
    try:
        user_email, user_name = await get_user_email(payment.username)
    except HTTPException as e:
        raise e  # Return the same error if fetching the user email fails

    # Step 1: Create a Stripe Checkout Session
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': payment.username,  # Use fetched username for product name
                    },
                    'unit_amount': int(payment.amount * 100),  # Use payment amount in cents
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
        username=payment.username,
        email=user_email,  # Use fetched email
        amount=payment.amount,  # Use payment amount
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
        "username": db_payment.username,
        "order_id": db_payment.order_id,
        "amount": db_payment.amount,
        "status": db_payment.status,
        "user_email": user_email,  # Include user email in the Kafka message
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    await producer.send_and_wait("payment_events", payment_message)

    return {"checkout_url": checkout_session.url}

# Simulate payment confirmation
async def confirm_payment(session_id: str):
    await asyncio.sleep(5)  # Simulate some delay for payment confirmation
    return True  # In real use, confirm with Stripe or listen to a webhook

@app.get("/payment-details/{order_id}")
async def get_payment_details(order_id: int):
    # Functionality to fetch and return payment details by order_id
    payment = session.get(Payment, order_id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment with ID '{order_id}' not found.")
    
    return payment
