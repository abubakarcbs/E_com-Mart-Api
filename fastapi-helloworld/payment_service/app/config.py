# payment_service/app/config.py

from pydantic import BaseSettings

class Settings(BaseSettings):
    kafka_broker: str = "localhost:9092"
    payment_topic: str = "payment-topic"
    database_url: str = "sqlite:///./payments.db"

    class Config:
        env_file = ".env"

settings = Settings()
