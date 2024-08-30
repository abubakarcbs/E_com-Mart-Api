import requests

NOTIFICATION_SERVICE_URL ="http://notification_service:8000/send-email/"

def send_registration_email(user_email: str, username: str):
    payload = {
        "email": "ranaalir986@gmail.com",  # Corrected key
        "subject": "New User Registration",
        "message": f"A new user has registered.\n\nUsername: {username}\nEmail: {user_email}"
    }
    try:
        response = requests.post(NOTIFICATION_SERVICE_URL, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        # Log the error appropriately
        print(f"Failed to send registration email: {e}")
        return False
