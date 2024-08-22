from fastapi import APIRouter,Depends
from app.controllers.crud_user import user_add
from typing import Annotated
from app.model.user_models import UserModel
 

router = APIRouter()

@router.get("/users")
def get_user():
    ...
    
    
@router.post("/add_user")
def add_user(user:Annotated[UserModel, Depends(user_add)]):
    return user
    

@router.put("/update_usre")
def update_user():
    ...
    
@router.delete("/delete_user")
def delete_user():
    ...