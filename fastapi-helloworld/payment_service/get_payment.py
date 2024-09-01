import logging
import requests
from sqlmodel import Session



async def fetch_order_data(order_id: int):
    order_service_url = f"http://order_service:8003/order/{order_id}"
    
    try:
        response = requests.get(order_service_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve order data: {e}")
        return None

async def fetch_user_data(user_id: int):
    user_service_url = f"http://user_services:8005/user/{user_id}"  # Adjust the URL as needed
    
    try:
        logging.info(f"Fetching user data for user_id: {user_id} from {user_service_url}")
        response = requests.get(user_service_url)
        response.raise_for_status()  # Will raise an HTTPError for bad responses (4xx, 5xx)
        
        user_data = response.json()  # Assuming the user_service returns JSON data
        logging.info(f"User data retrieved: {user_data}")
        return {
            "username": user_data["username"],  # Adjust these keys based on what the API returns
            "email": user_data["email"]
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch user data for user_id '{user_id}': {e}")
        return None
