# payment_service/app/main.py

from fastapi import FastAPI, Depends
from app.db.db import create_tables, get_session
from app.db import setting
from app.model import Payment
from payment_processor import process_payment
from app.kafka.kafka_producer import KafkaPaymentProducer
from sqlmodel import Session

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_tables()

producer = KafkaPaymentProducer()

@app.get("/")
async def root():
    return {"message": "Payment service is running!"}

@app.post("/process_payment/")
async def create_payment(user_id: str, order_id: str, amount: float, session: Session = Depends(get_session)):
    payment = process_payment(user_id, order_id, amount)
    producer.produce_message(setting.payment_topic, key=str(payment.id), value=f"Payment {payment.status}")
    return payment
