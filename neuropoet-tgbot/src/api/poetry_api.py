from dotenv import load_dotenv

import requests
import os


class PoetryAPI:
    def __init__(self):
        self.base_url = os.getenv("NPB_POETRY_API_BASE_URL")
        self.health_timeout = 2

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
    available = PoetryAPI().check_health()
    print(f"Poetry API is {"" if available else "un"}available")
