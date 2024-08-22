# notification_service/app/kafka_consumer.py

from app.db.db import get_session
from model import Notification
from sqlmodel import Session

def send_notification(notification_data: dict):
    with next(get_session()) as session:
        notification = Notification(**notification_data)
        session.add(notification)
        session.commit()
        session.refresh(notification)
        print(f"Notification saved and sent: {notification.message}")
