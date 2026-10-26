import asyncio
import random
from asyncio import Semaphore

from get_spisok import get_spisok
from login import AuthManager
from main_book import download_single_book


async def run_download_process(mode: str, url: str, do_ocr: bool):
    """
    Выполняет скачивание без input(). Все параметры приходят из GUI.
    """
    async with AuthManager() as auth:
        sema = Semaphore(4)

        if mode == 'single':
            if not url:
                print("Ссылка не введена!")
                return
            else:
                print("Начинаю скачку")
            await download_single_book(
                book_url=url, 
                session=auth.session, 
                sema=sema, 
                do_ocr=do_ocr
            )

        elif mode == 'excel':
            urls = get_spisok()  # твоя функция чтения Excel
            if not urls:
                print("Список ссылок пуст.")
                return

            print(f"В очереди {len(urls)} книг.")
            success = 0
            
            for i, u in enumerate(urls, 1):
                print(f"\n[{i}/{len(urls)}] Обработка: {u}")
                ok = await download_single_book(
                    book_url=u, 
                    session=auth.session, 
                    sema=sema, 
                    do_ocr=do_ocr)
                if ok:
                    success += 1
                
                if i < len(urls):
                    delay = random.uniform(20, 40)
                    print(f"Пауза {delay:.1f} сек...")
                    await asyncio.sleep(delay)
            
            print(f"\nИТОГО: Скачано {success} из {len(urls)}")