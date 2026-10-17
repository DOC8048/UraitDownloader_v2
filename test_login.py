# test_auth.py
import asyncio

from login import AuthManager


async def test():
    async with AuthManager() as auth:
        print("Мы внутри. Сессия готова.")
        # Тут можно сделать запрос через auth.session
        assert auth.session is not None
        async with auth.session.get("https://urait.ru/cabinet/profile") as resp:
            print(f"Статус профиля: {resp.status}")

asyncio.run(test())