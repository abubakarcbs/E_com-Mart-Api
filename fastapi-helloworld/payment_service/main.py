from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, SQLModel, create_engine
from app.model import Payment, PaymentCreate
from notification import send_payment_confirmation_email
from app.db.db import create_tables, engine
import stripe
from dotenv import load_dotenv
import os
from aiokafka import AIOKafkaProducer
import json
import asyncio

# Load environment variables from a .env file
load_dotenv()

# Stripe API keys from environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

stripe.api_key = STRIPE_SECRET_KEY

# Context manager to manage the lifespan of the FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables..")
    create_tables()
    yield

# FastAPI application instance with lifespan management
app = FastAPI(lifespan=lifespan)

# Dependency to get the database session
def get_session():
    with Session(engine) as session:
        yield session

# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

@app.get("/")
def welcome():
    return {"welcome": "Payment Service"}

class PaymentIntentCreate(BaseModel):
    amount: int  # Amount in cents (e.g., $10.00 -> 1000 cents)
    currency: str  # Currency code (e.g., 'usd')
    payment_method_types: list = ["card"]

@app.post("/create-payment-intent/")
def create_payment_intent(payment_data: PaymentIntentCreate):
    try:
        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=payment_data.amount,
            currency=payment_data.currency,
            payment_method_types=payment_data.payment_method_types
        )
        return {"client_secret": intent.client_secret}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/process-payment/")
async def process_payment(
    payment: PaymentCreate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Simulate payment processing
    payment_status = "success"  # This can be updated based on actual payment status from Stripe
    
    # Create payment record in the database
    db_payment = Payment(
        email=payment.email,
        name=payment.name,
        order_id=payment.order_id,
        amount=payment.amount,
        status=payment_status
    )
    session.add(db_payment)
    session.commit()
    session.refresh(db_payment)

    # Send payment confirmation email
    email_sent = send_payment_confirmation_email(
        email=db_payment.email,
        name=db_payment.name,
        order_id=db_payment.order_id,
        amount=db_payment.amount,
        status=db_payment.status
    )
    if not email_sent:
        print("Payment processed but failed to send confirmation email.")

    # Kafka message for processed payment
    payment_message = json.dumps({
        "event": "payment_processed",
        "payment_id": db_payment.id,
        "email": db_payment.email,
        "name": db_payment.name,
        "order_id": db_payment.order_id,
        "amount": db_payment.amount,
        "status": db_payment.status,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    await producer.send_and_wait("payment_events", payment_message)

    return {"status": db_payment.status, "payment_id": db_payment.id}
