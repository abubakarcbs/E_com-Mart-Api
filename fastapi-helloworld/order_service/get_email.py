import logging
import requests
from fastapi import HTTPException

def get_user_email(username: str) -> str:
    user_service_url = f"http://user_services:8005/user/{username}"  # Correct URL
    
    try:
        logging.info(f"Fetching user email for user ID {username} from {user_service_url}")
        response = requests.get(user_service_url)
        if response.status_code == 404:
            logging.warning(f"User with ID '{username}' not found.")
            raise HTTPException(status_code=404, detail=f"User with ID '{username}' not found.")
        response.raise_for_status()
        
        # Extracting email from the response
        user_data = response.json()
        logging.info(f"Successfully fetched user email: {user_data['email']}")
        return user_data["email"]
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to retrieve email for user ID '{username}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve email for user ID '{username}': {e}")

