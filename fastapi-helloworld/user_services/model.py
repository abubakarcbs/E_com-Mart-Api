from typing import Annotated
from fastapi import Form
from pydantic import BaseModel
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    userid: int = Field(default=None, primary_key=True)
    username: str
    email: str
    password: str
    role: str = Field(default="user")  # Add a role field, default is 'user'

class Register_User(BaseModel):
    username: Annotated[str, Form()]
    email: Annotated[str, Form()]
    password: Annotated[str, Form()]
    role: Annotated[str, Form()] = "user"  # Allow role assignment during registration

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class TokenData(BaseModel):
    username: str
    
class RefreshTokenData(BaseModel):
    email: str
