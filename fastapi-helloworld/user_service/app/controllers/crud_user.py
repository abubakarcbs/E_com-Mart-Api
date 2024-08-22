from sqlmodel import Session,select
from app.model.user_models import User, UserModel
from app.db.db_connector import DB_SESSION


def user_add(user_details: UserModel,session: DB_SESSION):
    db_statement = select(User).where(User.user_email == user_details.user_email).where(User.user_password == user_details.user_password).one_or_none()
    db_user_info = session.exec(db_statement).one_or_none()
    if db_user_info:
        print("user already exist")
    else:
        user = session(User)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user_details
        
    