# payment_service/main.py
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session
from app.model import Payment, PaymentCreate
from notification import send_payment_confirmation_email
from app.db.db import create_tables, engine
import stripe
from dotenv import load_dotenv
import os
from aiokafka import AIOKafkaProducer
import json
import asyncio
from contextlib import asynccontextmanager

# Load environment variables from a .env file
load_dotenv()

# Stripe API keys from environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

stripe.api_key = STRIPE_SECRET_KEY

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables..")
    create_tables()
    yield

app = FastAPI(lifespan=lifespan, title="Hello World API with Order", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8007", # ADD NGROK URL Here Before Creating GPT Action
            "description": "Development Server"
        }
        ]
        )

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

@app.post("/process-payment/")
async def process_payment(
    payment: PaymentCreate, 
    session: Session = Depends(get_session),
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    # Step 1: Create a Stripe Checkout Session
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': payment.name,
                    },
                    'unit_amount': int(payment.amount * 100),
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
        name=payment.name,
        email=payment.email,
        amount=payment.amount,
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
        "email": db_payment.email,
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

        # Send payment confirmation email with status 'paid'
        email_sent = send_payment_confirmation_email(
            email=db_payment.email,
            name=db_payment.name,
            order_id=db_payment.order_id,
            amount=db_payment.amount,
            status=db_payment.status
        )
        if not email_sent:
            print("Payment confirmation email failed to send.")

        # Prepare Kafka message for the confirmed payment
        payment_message = json.dumps({
            "event": "payment_confirmed",
            "payment_id": db_payment.id,
            "email": db_payment.email,
            "name": db_payment.name,
            "order_id": db_payment.order_id,
            "amount": db_payment.amount,
            "status": db_payment.status,
            "timestamp": asyncio.get_event_loop().time()
        }).encode("utf-8")

        await producer.send_and_wait("payment_events", payment_message)

    return {"checkout_url": checkout_session.url}

async def confirm_payment(session_id: str):
    # Simulate payment confirmation process
    await asyncio.sleep(5)  # Simulate some delay for payment confirmation
    return True  # In a real application, you would query Stripe or listen to a webhook
