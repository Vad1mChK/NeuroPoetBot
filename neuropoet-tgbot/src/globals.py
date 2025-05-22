# globals.py
from functools import lru_cache
from .api.emotion_api import EmotionAPI
from .api.poetry_api import PoetryAPI
from .database.database import Database
import aiohttp


class GlobalState:
    def __init__(self):
        self._emotion_api = None
        self._poetry_api = None
        self._database = None
        self._session = None

    async def get_emotion_api(self) -> EmotionAPI:
        if not self._emotion_api:
            self._session = aiohttp.ClientSession()
            self._emotion_api = EmotionAPI(self._session)
        return self._emotion_api

    async def get_poetry_api(self) -> PoetryAPI:
        if not self._poetry_api:
            self._session = aiohttp.ClientSession()
            self._poetry_api = PoetryAPI(self._session)
        return self._poetry_api

    async def get_database(self) -> Database:
        if not self._database:
            self._database = Database()
        return self._database

    async def close(self):
        if self._session:
            await self._session.close()
        if self._database:
            self._database.engine.dispose()


@lru_cache(maxsize=None)
def get_global_state() -> GlobalState:
    return GlobalState()
