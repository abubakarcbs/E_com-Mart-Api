# notification_service/app/main.py

from fastapi import FastAPI, Depends
from .db import create_db_and_tables, get_session
from model import Notification
from kafka.kafka_consumer import KafkaNotificationConsumer
import threading
from sqlmodel import Session

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

# Initialize Kafka Consumer in a separate thread
def start_consumer():
    consumer = KafkaNotificationConsumer()
    consumer.consume_notifications()

consumer_thread = threading.Thread(target=start_consumer)
consumer_thread.start()

@app.get("/")
async def root():
    return {"message": "Notification service is running!"}

@app.post("/notifications/")
async def create_notification(notification: Notification, session: Session = Depends(get_session)):
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification
