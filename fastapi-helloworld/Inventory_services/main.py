import asyncio
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from fastapi import FastAPI, HTTPException, Depends
from sqlmodel import Session, select
from app.db.db import get_session, create_tables
from app.model.inventory_model import Inventorys, InventoryUpdate
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Inventory Service API", 
              version="0.0.1",
              servers=[
                  {
                      "url": "http://localhost:8001",
                      "description": "Development Server"
                  }
              ])

# Initialize Kafka Producer
producer = AIOKafkaProducer(bootstrap_servers='broker:19092')

@app.on_event("startup")
async def startup_event():
    logging.info('Creating Tables...')
    create_tables()
    
    logging.info("Tables Created...")
    
    # Start the Kafka producer
    await producer.start()
    
    # Start Kafka consumers
    asyncio.create_task(consume_order_messages())
    asyncio.create_task(consume_product_messages())

@app.on_event("shutdown")
async def shutdown_event():
    # Stop the Kafka producer
    await producer.stop()

    logging.info("Kafka producer stopped")

@app.get("/")
def welcome():
    return {"welcome": "Inventory Page"}

@app.get("/inventory/all", response_model=list[Inventorys])
async def get_all_inventory(session: Session = Depends(get_session)):
    inventories = session.exec(select(Inventorys)).all()
    return inventories

@app.put("/inventory/{inventory_id}", response_model=Inventorys)
async def update_inventory(
    inventory_id: int, 
    inventory: InventoryUpdate, 
    session: Session = Depends(get_session)
):
    db_inventory = session.get(Inventorys, inventory_id)
    
    if not db_inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    for field, value in inventory.dict().items():
        setattr(db_inventory, field, value)
    session.commit()
    session.refresh(db_inventory)
    
    await producer.send_and_wait("inventory_topic", f"Updated: {db_inventory.id}".encode('utf-8'))
    logging.info(f"Sent update message for inventory_id {db_inventory.id} to inventory_topic")

    return db_inventory

@app.get("/inventory/{inventory_id}", response_model=Inventorys)
async def get_inventory(inventory_id: int, session: Session = Depends(get_session)):
    inventory = session.get(Inventorys, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory

@app.delete("/inventory/{inventory_id}", response_model=Inventorys)
async def delete_inventory(inventory_id: int, session: Session = Depends(get_session)):
    inventory = session.get(Inventorys, inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    session.delete(inventory)
    session.commit()

    return inventory

async def consume_order_messages():
    consumer = AIOKafkaConsumer(
        'order_topic',
        bootstrap_servers='broker:19092',
        group_id="inventory-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            order_data = json.loads(msg.value.decode('utf-8'))
            logging.info(f"Received order data: {order_data}")
            
            session = next(get_session())
            product_id = order_data['product_id']
            inventory_item = session.get(Inventorys, product_id)
            
            if inventory_item and inventory_item.quantity >= order_data['quantity']:
                # Reserve the inventory
                inventory_item.quantity -= order_data['quantity']
                session.commit()

                # Send inventory confirmation
                response = {
                    "order_id": order_data['order_id'],
                    "is_available": True
                }
                logging.info(f"Reserved inventory for product {product_id}, order {order_data['order_id']}")
            else:
                # Inventory not available
                response = {
                    "order_id": order_data['order_id'],
                    "is_available": False
                }
                logging.warning(f"Inventory not available for product {product_id}, order {order_data['order_id']}")

            # Send the response back to the order service
            response_json = json.dumps(response).encode('utf-8')
            await producer.send_and_wait("inventory_response_topic", response_json)
            logging.info(f"Sent inventory response for order {order_data['order_id']}")
    finally:
        await consumer.stop()


async def consume_product_messages():
    consumer = AIOKafkaConsumer(
        'product_topic',
        bootstrap_servers='broker:19092',
        group_id="inventory-group"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            product_data = json.loads(msg.value.decode('utf-8'))
            logging.info(f"Received product data: {product_data}")
            add_product_to_inventory(product_data)  # Add product to inventory
    finally:
        await consumer.stop()

def reserve_inventory(order_data):
    product_id = order_data['product_id']
    required_quantity = order_data['quantity']
    session = next(get_session())
    inventory_item = session.get(Inventorys, product_id)
    
    if inventory_item and inventory_item.quantity >= required_quantity:
        inventory_item.quantity -= required_quantity  # Reserve inventory
        session.commit()  # Commit the changes to the database
        logging.info(f"Reserved {required_quantity} of product_id {product_id}")
        return True
    logging.warning(f"Failed to reserve {required_quantity} of product_id {product_id}")
    return False

def add_product_to_inventory(product_data):
    session = next(get_session())
    new_product = Inventorys(**product_data)
    session.add(new_product)
    session.commit()
    logging.info(f"Added new product to inventory: {new_product}")
