from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str

    # Microsoft Azure / Graph
    azure_client_id: str
    azure_client_secret: str
    azure_tenant_id: str
    azure_redirect_uri: str

    # WhatsApp / Meta
    meta_app_id: str
    meta_app_secret: str
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    whatsapp_verify_token: str

    # Database (auto-injected by Railway plugins)
    database_url: str
    redis_url: str

    # App
    railway_public_domain: str
    secret_key: str
    environment: str = "production"
    log_level: str = "INFO"


settings = Settings()
