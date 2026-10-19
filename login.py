
import json
import logging
import os

import environ
from aiohttp import ClientSession
from yarl import URL

COOKIES_FILE = "session_cookies.json"
LOG = 'urait.log'
BASE_URL = URL("https://urait.ru")
DEFAULT_HEADERS = {
    'Host': 'urait.ru',
    'Origin': 'https://urait.ru',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36'
}
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
    handlers=[
        logging.FileHandler(LOG, encoding='utf-8', mode='w'),
    ]
)
logger = logging.getLogger(__name__)
class AuthManager:
    def __init__(self) -> None:
        env = environ.Env()
        environ.Env.read_env('account.txt')
        self.session = None
        # self.semaphore = semaphore
        self.email = env('URAIT_EMAIL')
        self.password = env('URAIT_PASSWORD')
    async def __aenter__(self):
        """Вызывается на входе в блок 'async with'"""
        self.session = ClientSession(headers=DEFAULT_HEADERS)
        success = await self.ensure_authorized()
        if not success:
            await self.session.close()
            raise PermissionError("Не удалось авторизоваться. Проверь account.txt")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Вызывается на выходе из блока 'async with' — даже если была ошибка"""
        if self.session:
            await self.session.close()

    async def login(self):
        '''Функция для авторизации пользователя'''
        print("Авторизация пользователя...")
        assert self.session is not None
        response = await self.session.post(
            'https://urait.ru/login',
            json={'email': self.email, 'password': self.password},
            allow_redirects=False
        )
        status = response.status
        location = response.headers.get('Location', '')
        if status == 302 and '/login' in location:
            logger.warning('Неверный пароль')
            return False

        logger.info('Авторизация прошла успешно')
        await self.save_cookies()
        return True

    async def save_cookies(self):
        """Сохраняет куки из сессии в JSON-файл.""" 
        cookies = {}
        assert self.session is not None
        for cookie in self.session.cookie_jar:
                cookies[cookie.key] = {
                    "value": cookie.value,
                }   
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            json.dump(cookies, f, ensure_ascii=False)
        logger.info(f"Куки сохранены в {COOKIES_FILE}")


    def load_cookies(self) -> bool:
        """Загружает куки из JSON-файла в сессию. Возвращает True, если файл есть."""
        if not os.path.exists(COOKIES_FILE):
            return False
        with open(COOKIES_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for key, data in cookies.items():
            assert self.session is not None
            self.session.cookie_jar.update_cookies(
                {key: data["value"]},
            response_url=BASE_URL
        )
        logger.info(f"Куки загружены из {COOKIES_FILE}")
        return True
    

    async def check_authorized(self) -> bool:
        """Делает контрольный запрос, чтобы проверить, жива ли сессия."""
        try:
            assert self.session is not None
            async with self.session.get(
            "https://urait.ru/cabinet/profile",
            allow_redirects=False,
            ) as resp:
            # Если 200 — мы внутри. Если 302 на /login — сессия протухла.
                if resp.status == 200:
                    return True
                if resp.status == 302 and "/login" in resp.headers.get("Location", ""):
                    return False
            return False
        except Exception:
            return False
    
    async def ensure_authorized(self):
        if self.load_cookies() and await self.check_authorized():
            logger.info("✅ Сессия активна (куки загружены)")
            return True

        logger.warning("⚠️ Куки протухли, делаем повторный логин")
        return await self.login()
