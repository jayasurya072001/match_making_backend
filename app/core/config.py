from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str
    MONGO_URI: str
    MONGO_DB_NAME: str
    MONGO_CHAT_DB: str
    MONGO_PERSONALITY_DB: str
    MONGO_ACCOUNTS_DB: str
    MONGO_MATCHMAKING_PROFILES_DB: str
    REDIS_URL: str
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_CHAT_TOPIC: str
    KAFKA_RESPONSE_TOPIC: str
    KAFKA_STATUS_TOPIC: str
    LOG_LEVEL: str
    MCP_SERVER_SCRIPT: str
    ELEVEN_LABS_API_KEY: str
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str
    AZURE_OPENAI_ENDPOINT : str
    AZURE_DEPLOYMENT : str
    AZURE_API_KEY : str
    AZURE_API_VERSION : str
    PERPLEXITY_API_KEY : str
 

    class Config:
        env_file = ".env"

settings = Settings()
