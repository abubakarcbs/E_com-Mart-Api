from passlib.context import CryptContext
from sqlmodel import Session, select
from sqlmodel import SQLModel
from typing import Annotated
from app.db import get_session
from fastapi import Depends, HTTPException, status
from model import RefreshTokenData, TokenData, User
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import datetime, timezone, timedelta
import httpx



SECRET_KEY = 'ed60732905aeb0315e2f77d05a6cb57a0e408eaf2cb9a77a5a2667931c50d4e0'
ALGORITHYM = 'HS256'
EXPIRY_TIME = 1

oauth_scheme = OAuth2PasswordBearer(tokenUrl="/token")

pwd_context = CryptContext(schemes="bcrypt")



def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hash_password):
    return pwd_context.verify(password, hash_password)


def get_user_from_db(session: Annotated[Session, Depends(get_session)],
                     username: str | None = None,
                     email: str | None = None):
    statement = select(User).where(User.username == username)
    user = session.exec(statement).first()
    print(user)
    if not user:
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        if user:
            return user

    return user


def authenticate_user(username,
                      password,
                      session: Annotated[Session, Depends(get_session)]):
    db_user = get_user_from_db(session=session, username=username)
    print(f""" authenticate {db_user} """)
    if not db_user:
        return False
    if not verify_password(password, db_user.password):
        return False
    return db_user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    
    # Include user role in the token
    to_encode.update({"role": data.get("role")})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHYM)
    return encoded_jwt



def current_user(token: Annotated[str, Depends(oauth_scheme)],
                 session: Annotated[Session, Depends(get_session)]):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token, Please login again",
        headers={"www-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHYM)
        username: str | None = payload.get("sub")

        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)

    except JWTError:
        raise credential_exception
    user = get_user_from_db(session, username=token_data.username)
    if not user:
        raise credential_exception
    return user


def create_refresh_token(data: dict, expiry_time: timedelta | None):
    data_to_encode = data.copy()
    if expiry_time:
        expire = datetime.now(timezone.utc) + expiry_time
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    data_to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        data_to_encode, SECRET_KEY, algorithm=ALGORITHYM, )
    return encoded_jwt


def validate_refresh_token(token: str,
                           session: Annotated[Session, Depends(get_session)]):

    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token, Please login again",
        headers={"www-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, ALGORITHYM)
        email: str | None = payload.get("sub")
        if email is None:
            raise credential_exception
        token_data = RefreshTokenData(email=email)

    except:
        raise JWTError
    user = get_user_from_db(session, email=token_data.email)
    if not user:
        raise credential_exception
    return user


def check_role(required_role: str):
    def role_checker(session: Annotated[Session, Depends(get_session)], token: str = Depends(oauth_scheme)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHYM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            user = get_user_from_db(session, username=username)
            if user is None or user.role != required_role:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
        except JWTError:
            raise credentials_exception
    return role_checker












# SECRET_KEY = "DPZau2JXU0OnZXMYKjgOOAQbXgGRNknZ"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2
class TokenData(SQLModel):
    iss: str

def get_secret_from_kong(consumer_id: str) -> str:
    with httpx.Client() as client:
        print(f'consumer_id: {consumer_id}')
        url = f"http://kong:8001/consumers/{consumer_id}/jwt"
        response = client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code,
                                detail="Failed to fetch secret from Kong")
        kong_data = response.json()
        print(f'Kong Data: {kong_data}')
        if not kong_data['data'][0]["secret"]:
            raise HTTPException(
                status_code=404, detail="No JWT credentials found for the specified consumer")

        secret = kong_data['data'][0]["secret"]
        print(f'Secret: {secret}')
        return secret






def create_jwt_token(data: dict, secret: str):
    to_encode = data.copy()
    expire = datetime.utcnow() + \
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Limit expiration time to 2038-01-19 03:14:07 UTC
    expire = min(expire, datetime(2038, 1, 19, 3, 14, 7))
    to_encode.update({"exp": expire})
    headers = {
        "typ": "JWT",
        "alg": ALGORITHM
    }
    encoded_jwt = jwt.encode(to_encode, secret,
                             algorithm=ALGORITHM, headers=headers)
    return encoded_jwt

