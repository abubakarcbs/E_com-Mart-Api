# payment_service/app/payment_processor.py

from app.model import Payment
from app.db.db import get_session
from sqlmodel import Session

def process_payment(user_id: str, order_id: str, amount: float):
    with next(get_session()) as session:
        payment = Payment(user_id=user_id, order_id=order_id, amount=amount, status="Processing")
        session.add(payment)
        session.commit()
        session.refresh(payment)
        
        # Simulate payment gateway interaction
        payment.status = "Completed"
        session.add(payment)
        session.commit()
        session.refresh(payment)
        
        return payment
