from sqlmodel import create_engine, Session
from .config import get_settings


settings = get_settings()

engine = create_engine(settings.DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session