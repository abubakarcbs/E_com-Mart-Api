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

@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables')
    create_tables()
    print("Tables Created")
    yield

app: FastAPI = FastAPI(
    lifespan=lifespan, title="Welcome to user services", version='1.0.0')

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

# Login endpoint with Kafka integration
@app.post('/token', response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
    producer: AIOKafkaProducer = Depends(get_kafka_producer)
):
    user = authenticate_user(form_data.username, form_data.password, session)
    if not user:
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

    await producer.send_and_wait("user_events", login_message)

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

    await producer.send_and_wait("user_events", refresh_message)

    return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)
