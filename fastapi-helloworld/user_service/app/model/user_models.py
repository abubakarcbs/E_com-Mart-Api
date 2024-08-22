from sqlmodel import SQLModel,Field
from pydantic import Emailstr
from typing import Optional

class UserBase(SQLModel):
    user_name : str
    phone_number : int = Field(max_digits = 11)
   
   
class UserAuth(SQLModel):
    user_email : Emailstr
    user_password : str
    
class UserModel(UserAuth,UserBase):
    pass 

user = UserModel()

class User(UserModel,table= True):
    user_id : Optional[int] = Field(str,primary_key = True)
