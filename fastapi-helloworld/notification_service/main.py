from sqlmodel import Session
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import os
import asyncio
from aiokafka import AIOKafkaConsumer
from contextlib import asynccontextmanager
import json
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.db.db import get_session
import re  # Import regex module for email validation

# Set up logging
logging.basicConfig(level=logging.INFO)

# Replace with your actual Gmail credentials and App Password
GMAIL_USER = os.getenv("GMAIL_USER", "muhammadabubakarcbs@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "zfzz rhbj dpey nopv")  # Ensure this is set securely

class EmailSchema(BaseModel):
    email: EmailStr
    subject: str
    message: str

app = FastAPI()

def is_valid_email(email: str) -> bool:
    # Simple regex for validating an email
    return re.match(r"[^@]+@[^@]+\.[^@]+", email) is not None

async def send_email(to_email: str, subject: str, message: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        # Correcting the call to aiosmtplib.send
        await aiosmtplib.send(
            msg,  # The message object should be passed positionally
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=GMAIL_USER,
            password=GMAIL_PASSWORD,
        )

        logging.info(f"Email sent to {to_email} successfully.")
        return "Email sent successfully"
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Kafka Consumers for user events, order events, and payment events
    events_consumer_task = asyncio.create_task(consume_events())
    yield
    # Ensure the consumer tasks are properly handled on shutdown
    events_consumer_task.cancel()
    await events_consumer_task

app = FastAPI(lifespan=lifespan)

async def consume_events():
    consumer = AIOKafkaConsumer(
        'user_events', 'order_events', 'payment_events',
        bootstrap_servers='broker:19092',
        group_id="notification-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            try:
                event_data = json.loads(msg.value.decode('utf-8'))
                logging.info(f"Received event: {event_data}")

                # Skip order_creation events
                if event_data['event'] == 'order_creation':
                    logging.info(f"Skipping event: {event_data['event']}")
                    continue

                # Process inventory_check events
                elif event_data['event'] == 'inventory_check':
                    user_email = event_data.get('user_email')
                    order_status = event_data.get('status')
                    
                    if not user_email or not is_valid_email(user_email):
                        logging.error(f"Invalid or missing 'user_email' in event: {event_data}")
                        continue  # Skip processing this event
                    
                    # Customize the email subject and message based on the order status
                    if order_status == "Placed":
                        subject = "Order Placed Successfully"
                        message = f"Your order with ID {event_data['order_id']} has been placed successfully."
                    elif order_status == "Failed":
                        subject = "Order Placement Failed"
                        message = f"Unfortunately, your order with ID {event_data['order_id']} could not be placed due to inventory issues."
                    else:
                        subject = "Order Status Update"
                        message = f"Your order with ID {event_data['order_id']} is currently {order_status}."

                    # Send the email
                    await send_email(user_email, subject, message)

                # Handle payment processed events if needed (optional)
                elif event_data['event'] == 'payment_processed':
                    user_email = event_data.get('user_email')
                    if not user_email or not is_valid_email(user_email):
                        logging.error(f"Invalid or missing 'user_email' in event: {event_data}")
                        continue  # Skip processing this event
                    subject = "Payment Confirmation"
                    message = f"Your payment for order ID {event_data['order_id']} has been processed successfully."
                    await send_email(user_email, subject, message)

            except Exception as e:
                logging.error(f"Failed to process message: {e}")
    finally:
        await consumer.stop()
