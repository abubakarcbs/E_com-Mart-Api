from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from auth import current_user, get_user_from_db, hash_password, oauth_scheme
from app.db import get_session
from model import Register_User, User
from notification import send_registration_email




user_router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}}
)

@user_router.get("/")
async def read_user():
    return {"message": "welcome to user service"}

@user_router.post("/register")
async def register_user(new_user: Annotated[Register_User, Depends()],
                        session: Annotated[Session, Depends(get_session)]):
    
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

    return {"message": f"User with {user.username} successfully registered"}

@user_router.get('/me')
async def user_profile (current_user:Annotated[User, Depends(current_user)]):

    return current_user