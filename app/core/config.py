from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MFW Sync Server"
    MONGO_URI: str = "mongodb://myuser:mypassword@48.217.49.77:27017"
    MONGO_DB_NAME: str = "match_making_profiles"
    MONGO_CHAT_DB: str = "match_making_chat"
    REDIS_URL: str = "redis://127.0.0.1:6379"
    KAFKA_BOOTSTRAP_SERVERS: str = "52.188.189.148:9092"
    # KAFKA_CHAT_TOPIC: str = "chat_requests"
    # KAFKA_RESPONSE_TOPIC: str = "chat_response"
    # TOPIC_STATUS: str = "chat_status"
    KAFKA_CHAT_TOPIC: str = "test_chat_requests"
    KAFKA_RESPONSE_TOPIC: str = "test_chat_response"
    KAFKA_STATUS_TOPIC: str = "test_chat_status"
    LOG_LEVEL: str = "INFO"
    MCP_SERVER_SCRIPT: str = "app/mcp/smrit_mcp_service.py"

    class Config:
        env_file = ".env"

settings = Settings()
