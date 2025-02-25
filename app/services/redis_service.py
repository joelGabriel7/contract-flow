import redis
from ..core.config import get_settings

settings = get_settings()


class RedisService:

    def __init__(self):

        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0
        )

    def add_to_blacklist(self, token: str, expires_in: int):
        self.redis.setex(f"blacklist:{token}", expires_in, "1")

    def is_blacklisted(self, token: str) -> bool:
        return bool(self.redis.get(f'blacklist:{token}'))  # CORRECT


redis_service = RedisService()
