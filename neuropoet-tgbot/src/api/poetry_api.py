from dataclasses import dataclass
import asyncio
import aiohttp
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class PoetryGenerationRequestDto:
    user_id: int
    emotions: dict[str, float]
    gen_strategy: str


@dataclass(frozen=True)
class PoetryGenerationResponseDto:
    poem: str
    gen_strategy: str


class PoetryAPI:
    def __init__(self, session: aiohttp.ClientSession = None):
        self.base_url = os.getenv("NPB_POETRY_API_BASE_URL")
        self.default_timeout = int(os.getenv("NPB_POETRY_API_TIMEOUT", "5"))
        self.session = session or aiohttp.ClientSession()
        self.health_timeout = 2

    async def check_health(self) -> bool:
        """Check if Poetry API service is available"""
        try:
            async with self.session.get(
                    f"{self.base_url}/health",
                    timeout=self.health_timeout
            ) as response:
                return 200 <= response.status < 300
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def generate_poem(self, request: PoetryGenerationRequestDto) -> PoetryGenerationResponseDto:
        try:
            async with self.session.post(
                    f"{self.base_url}/generate",
                    json={
                        "user_id": request.user_id,
                        "emotions": request.emotions,
                        "gen_strategy": request.gen_strategy,
                    },
                    timeout=self.default_timeout
            ) as response:
                data = await response.json()
                return PoetryGenerationResponseDto(poem=data["poem"], gen_strategy=data["gen_strategy"])
        except Exception as e:
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.session.close()


if __name__ == '__main__':
    async def main():
        load_dotenv()
        async with PoetryAPI() as api:
            available = await api.check_health()
            print(f"Poetry API is {'available' if available else 'unavailable'}")


    asyncio.run(main())
