from datetime import timedelta
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from fastapi import Depends, FastAPI, HTTPException,status
from contextlib import asynccontextmanager
from app.db import create_tables, get_session
from model import Token, User
from router import user
from auth import EXPIRY_TIME, authenticate_user, create_access_token, create_refresh_token, validate_refresh_token

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

# login . username, password
@app.post('/token', response_model=Token)
async def login(form_data:Annotated[OAuth2PasswordRequestForm, Depends()],
                session:Annotated[Session, Depends(get_session)]):
    user = authenticate_user (form_data.username, form_data.password, session)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    expire_time = timedelta(minutes=EXPIRY_TIME)
    access_token = create_access_token({"sub":form_data.username}, expire_time)

    refresh_expire_time = timedelta(days=7)
    refresh_token = create_refresh_token({"sub":user.email}, refresh_expire_time)

    return Token(access_token=access_token, token_type="bearer", refresh_token=refresh_token)


# Token Refresh 
@app.post("/token/refresh")
def refresh_token(old_refresh_token:str,
                  session:Annotated[Session, Depends(get_session)]):
    
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token, Please login again",
        headers={"www-Authenticate":"Bearer"}
    )
    
    user = validate_refresh_token(old_refresh_token,
                                  session)
    if not user:
        raise credential_exception
    
    expire_time = timedelta(minutes=EXPIRY_TIME)
    access_token = create_access_token({"sub":user.username}, expire_time)

    refresh_expire_time = timedelta(days=7)
    refresh_token = create_refresh_token({"sub":user.email}, refresh_expire_time)

    return Token(access_token=access_token, token_type= "bearer", refresh_token=refresh_token)