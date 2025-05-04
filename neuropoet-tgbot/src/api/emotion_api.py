from typing import Optional

from dotenv import load_dotenv
from dataclasses import dataclass

import requests
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
    def __init__(self):
        self.base_url = os.getenv("NPB_EMOTION_API_BASE_URL")
        self.health_timeout = 2

    def analyze_emotions(self, request: EmotionAnalyzeRequestDto) -> Optional[EmotionAnalyzeResponseDto]:
        """
        Analyze emotions in text
        Returns EmotionAnalyzeResponseDto if successful, None otherwise
        """
        try:
            response = requests.post(
                f"{self.base_url}/analyze",
                json={
                    "user_id": request.user_id,
                    "text": request.message
                },
                timeout=10
            )
            response.raise_for_status()

            return EmotionAnalyzeResponseDto(
                emotions=response.json()["emotions"]
            )
        except (requests.exceptions.RequestException, KeyError):
            return None

    def check_health(self) -> bool:
        """
        Check if Emotion API service is available
        Returns True if service responds successfully
        """
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=2
            )
            return 200 <= response.status_code < 300
        except requests.exceptions.RequestException:
            return False


if __name__ == '__main__':
    load_dotenv()
    available = EmotionAPI().check_health()
    print(f"Emotion API is {"" if available else "un"}available")