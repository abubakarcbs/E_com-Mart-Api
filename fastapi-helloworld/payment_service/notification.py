import requests

NOTIFICATION_SERVICE_URL = "http://127.0.0.1:8000/send-email/"

def send_payment_confirmation_email(email: str, name: str, order_id: int, amount: float, status: str):
    payload = {
          "email": "ranaalir986@gmail.com",  # Send to your email
        "subject": f"Payment Confirmation for Order #{order_id}",
        "message": f"Hello {name},\n\nYour payment of ${amount} for Order ID: {order_id} has been {status}."
    }
    try:
        response = requests.post(NOTIFICATION_SERVICE_URL, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send payment confirmation email: {e}")
        return False
