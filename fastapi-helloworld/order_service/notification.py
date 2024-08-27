import requests

NOTIFICATION_SERVICE_URL = "http://notification_service:8000/send-email/"


def send_order_confirmation_email(order_id: int, user_email: str, order_details: str):
    payload = {
        "email": "ranaalir986@gmail.com",  # Send to your email
        "subject": f"New Order Placed: #{order_id}",
        "message": f"An order has been placed.\n\nOrder ID: {order_id}\nUser Email: {user_email}\nOrder Details: {order_details}"
    }
    try:
        response = requests.post(NOTIFICATION_SERVICE_URL, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send order confirmation email: {e}")
        return False
