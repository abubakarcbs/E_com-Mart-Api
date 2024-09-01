import logging
import requests
from fastapi import HTTPException

def get_user_email(user_id: int) -> str:
    user_service_url = f"http://user_services:8005/user/{user_id}"  # Correct URL
    
    try:
        logging.info(f"Fetching user email for user ID {user_id} from {user_service_url}")
        response = requests.get(user_service_url)
        if response.status_code == 404:
            logging.warning(f"User with ID '{user_id}' not found.")
            raise HTTPException(status_code=404, detail=f"User with ID '{user_id}' not found.")
        response.raise_for_status()
        
        # Extracting email from the response
        user_data = response.json()
        logging.info(f"Successfully fetched user email: {user_data['email']}")
        return user_data["email"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve email for user ID '{user_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve email for user ID '{user_id}': {e}")

