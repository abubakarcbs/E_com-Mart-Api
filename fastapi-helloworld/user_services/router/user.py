import asyncio
import json
import logging
from typing import Annotated
from aiokafka.errors import KafkaError
from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from auth import check_role, current_user, get_user_from_db, hash_password, oauth_scheme
from app.db import get_session
from model import Register_User, User


user_router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)


# Kafka Producer as a dependency
async def get_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers='broker:19092')
    await producer.start()
    try:
        yield producer
    finally:
        await producer.stop()

# Function to produce Kafka messages with logging and exception handling
async def produce_kafka_message(producer, topic, message):
    try:
        logging.info(f"Attempting to send message to topic {topic}: {message}")
        await producer.send_and_wait(topic, message)
        logging.info(f"Message sent to topic {topic} successfully.")
    except KafkaError as e:
        logging.error(f"Failed to send message to Kafka: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message to Kafka.")


@user_router.post("/register")
async def register_user(new_user: Annotated[Register_User, Depends()],
                        session: Annotated[Session, Depends(get_session)],
                        producer: Annotated[AIOKafkaProducer, Depends(get_kafka_producer)]):
    
    db_user = get_user_from_db(session, new_user.username, new_user.email)
    if db_user:
        raise HTTPException(status_code=409, detail="User with these credentials already exists")
    
    user = User(
        username=new_user.username,
        email=new_user.email,
        password=hash_password(new_user.password)
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Send registration email notification
    email_sent = send_registration_email(user_email=user.email, username=user.username)
    if not email_sent:
        # Optionally handle the case where email sending fails
        print("Registration succeeded but failed to send notification email.")

    # Kafka message for successful registration
    registration_message = json.dumps({
        "event": "user_registration",
        "username": user.username,
        "email": user.email,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    # Produce Kafka message
    await produce_kafka_message(producer, "user_events", registration_message)

    return {"message": f"User with {user.username} successfully registered"}



@user_router.get('/me')
async def user_profile (current_user:Annotated[User, Depends(current_user)]):
    return current_user