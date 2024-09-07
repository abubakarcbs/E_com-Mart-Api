import httpx
from jose import jwt, JWTError  # Use 'jose' consistently for JWT decoding
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Define your OAuth2 scheme with the correct token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://user_services:8005/token")

async def fetch_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Validate the JWT token
        print(f"Received token: {token}")  # Log received token
        payload = jwt.decode(token, "your_secret_key", algorithms=["HS256"])
        print(f"Decoded payload: {payload}")  # Log decoded payload
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as e:
        print(f"JWT Error: {e}")  # Add detailed logging for JWT errors
        raise credentials_exception

    # Fetch user details from the user service
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"http://user_services:8005/api/user/{user_id}")
            print(f"User Service Response: {response.status_code} - {response.text}")  # Add detailed logging
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="User not found")
        except httpx.RequestError as e:
            print(f"Request Error: {e}")  # Add detailed logging for request errors
            raise HTTPException(status_code=502, detail="User service request failed")
