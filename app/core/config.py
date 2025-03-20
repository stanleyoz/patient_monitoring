from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Project paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    SESSIONS_DIR: Path = DATA_DIR / "sessions"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # IMU settings
    MEASUREMENT_UUID: str = "15172004-4947-11e9-8646-d663bd873d93"
    CONTROL_UUID: str = "15172001-4947-11e9-8646-d663bd873d93"
    SAMPLING_RATE: int = 60
    
    class Config:
        env_file = ".env"

settings = Settings()
