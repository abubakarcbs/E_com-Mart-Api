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

