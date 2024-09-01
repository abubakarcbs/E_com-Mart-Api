from datetime import timedelta
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from fastapi import Depends, FastAPI, HTTPException, status
from contextlib import asynccontextmanager
from app.db import create_tables, get_session
from model import Token, User
from router import user
from auth import EXPIRY_TIME, authenticate_user, create_access_token, create_refresh_token, validate_refresh_token
from aiokafka import AIOKafkaProducer
import json
import asyncio
import logging
from aiokafka.errors import KafkaError

# Set up logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info('Creating Tables...')
    create_tables()
    logging.info("Tables Created...")
    yield

app = FastAPI(lifespan=lifespan, title="User Service API", 
    version="0.0.1",
    servers=[
        {
            "url": "http://localhost:8005",
            "description": "Development Server"
        }
    ]
)

app.include_router(router=user.user_router)

@app.get('/')
async def root():
    return {"message": "Welcome to user services"}

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

# User registration endpoint with Kafka notification integration
@app.post('/register', response_model=User)
async def register_user(
    user: User, 
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    try:
        session.add(user)
        session.commit()
        session.refresh(user)
        logging.info(f"User registered successfully: {user.username}")
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to register user: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user.")

    # Kafka message for successful registration
    registration_message = json.dumps({
        "event": "user_registration",
        "username": user.username,
        "email": user.email,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    # Produce Kafka message with logging
    await produce_kafka_message(producer, "user_events", registration_message)

    return user

# Login endpoint with Kafka integration
@app.post('/token', response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
        logging.warning(f"Failed login attempt for username: {form_data.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    expire_time = timedelta(minutes=EXPIRY_TIME)
    access_token = create_access_token({"sub": form_data.username}, expire_time)

    refresh_expire_time = timedelta(days=7)
    refresh_token = create_refresh_token({"sub": user.email}, refresh_expire_time)

    # Kafka message for successful login
    login_message = json.dumps({
        "event": "user_login",
        "username": form_data.username,
        "email": user.email,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    # Produce Kafka message with logging
    await produce_kafka_message(producer, "user_events", login_message)

    return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)

# Token Refresh with Kafka integration
@app.post("/token/refresh")
async def refresh_token(
    old_refresh_token: str,
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token, Please login again",
        headers={"www-Authenticate": "Bearer"}
    )
    
    user = validate_refresh_token(old_refresh_token, session)
    if not user:
        logging.warning(f"Failed token refresh attempt for token: {old_refresh_token}")
        raise credential_exception
    
    expire_time = timedelta(minutes=EXPIRY_TIME)
    access_token = create_access_token({"sub": user.username}, expire_time)

    refresh_expire_time = timedelta(days=7)
    refresh_token = create_refresh_token({"sub": user.email}, refresh_expire_time)

    # Kafka message for token refresh
    refresh_message = json.dumps({
        "event": "token_refresh",
        "username": user.username,
        "email": user.email,
        "timestamp": asyncio.get_event_loop().time()
    }).encode("utf-8")

    # Produce Kafka message with logging
    await produce_kafka_message(producer, "user_events", refresh_message)

    return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)

@app.get("/user/{userid}")
def read_user(userid: int, db: Session = Depends(get_session)):
    user = db.query(User).filter(User.userid == userid).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID '{userid}' not found.")
    return user