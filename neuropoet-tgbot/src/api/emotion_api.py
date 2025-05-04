import asyncio
from typing import Optional

from dotenv import load_dotenv
from dataclasses import dataclass

import aiohttp
import os


load_dotenv()

@dataclass(frozen=True)
class EmotionAnalyzeRequestDto:
    user_id: int
    message: str


@dataclass(frozen=True)
class EmotionAnalyzeResponseDto:
    emotions: dict[str, float]


class EmotionAPI:
    def __init__(self, session: aiohttp.ClientSession = None):
        self.base_url = os.getenv("NPB_EMOTION_API_BASE_URL")
        self.default_timeout = int(os.getenv("NPB_EMOTION_API_TIMEOUT", "5"))
        self.session = session or aiohttp.ClientSession()
        self.health_timeout = 2

    async def analyze_emotions(self, request: EmotionAnalyzeRequestDto):
        try:
            async with self.session.post(
                f"{self.base_url}/analyze",
                json={
                    "user_id": request.user_id,
                    "text": request.message
                },
                timeout=self.default_timeout
            ) as response:
                data = await response.json()
                return EmotionAnalyzeResponseDto(emotions=data["emotions"])
        except Exception as e:
            return None

    async def check_health(self) -> bool:
        """
        Check if Emotion API service is available
        Returns True if service responds successfully
        """
        try:
            async with self.session.get(
                    f"{self.base_url}/health",
                    timeout=self.health_timeout
            ) as response:
                return 200 <= response.status < 300
        except Exception as e:
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.session.close()


if __name__ == '__main__':
    async def main():
        load_dotenv()
        async with aiohttp.ClientSession() as session:
            api = EmotionAPI(session)
            available = await api.check_health()
            print(f"Emotion API is {'available' if available else 'unavailable'}")


    asyncio.run(main())