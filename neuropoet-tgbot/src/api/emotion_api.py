from dotenv import load_dotenv
import os

load_dotenv()

class EmotionAPI:
    def __init__(self):
        self.base_url = os.getenv("NPB_EMOTION_API_BASE_URL")

if __name__ == '__main__':
    api = EmotionAPI()