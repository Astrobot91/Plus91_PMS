from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SHAREPRO_WIZZER_API_KEY: str

    class Config:
        env_file = "/home/admin/Plus91Backoffice/Plus91_Backend/.env"

settings = Settings()
