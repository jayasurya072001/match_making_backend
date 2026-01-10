from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MFW Sync Server"
    MONGO_URI: str = "mongodb://myuser:mypassword@48.217.49.77:27017"
    MONGO_DB_NAME: str = "match_making"
    MONGO_CHAT_DB: str = "match_making_chat"
    REDIS_URL: str = "redis://20.99.243.133:6379"
    KAFKA_BOOTSTRAP_SERVERS: str = "52.188.189.148:9092"
    # KAFKA_CHAT_TOPIC: str = "chat_requests"
    # KAFKA_RESPONSE_TOPIC: str = "chat_response"
    # TOPIC_STATUS: str = "chat_status"
    KAFKA_CHAT_TOPIC: str = "test_chat_requests"
    KAFKA_RESPONSE_TOPIC: str = "test_chat_response"
    KAFKA_STATUS_TOPIC: str = "test_chat_status"
    LOG_LEVEL: str = "INFO"
    ELEVEN_LABS_API_KEY="sk_b1501d96ada8beb1a995f82d350512f5b70a1d2ba3837d74"
    BLOB_STORAGE_CONNECTION="DefaultEndpointsProtocol=https;AccountName=mfwstorage1;AccountKey=nlkScjBwt8eg6A3dxg49Vyc2CGOfLYubJTx1lKotq7VQPDkJ0Xgorpxmoy+XnnegaW4WDL+G5cDt+AStlVHHBQ==;EndpointSuffix=core.windows.net"
    BLOB_STORAGE_CONTAINER="match-audio"

    class Config:
        env_file = ".env"

settings = Settings()
