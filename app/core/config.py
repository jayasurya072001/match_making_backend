from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str
    MONGO_URI: str
    MONGO_DB_NAME: str
    MONGO_CHAT_DB: str
    REDIS_URL: str
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_CHAT_TOPIC: str
    KAFKA_RESPONSE_TOPIC: str
    KAFKA_STATUS_TOPIC: str
    LOG_LEVEL: str
    MCP_SERVER_SCRIPT: str

    class Config:
        env_file = ".env"

settings = Settings()
