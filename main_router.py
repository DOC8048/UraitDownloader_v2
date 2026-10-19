import asyncio
import random
import sys
from asyncio import Semaphore

from get_spisok import get_spisok
from login import AuthManager
from main_book import download_single_book


async def main():
    # 1. Спрашиваем режим (если не передан флаг --test)
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        mode = 'test'
        print("[TEST MODE] Использую тестовую книгу")
    else:
        print("\nВыберите режим:")
        print("  1. Одна книга по ссылке")
        print("  2. Пакет книг из Excel")
        choice = input("Ваш выбор (1/2, Enter = 1): ").strip()
        mode = 'excel' if choice == '2' else 'single'
    # 2. Спрашиваем про OCR (один раз для всех режимов)
    # В тестовом режиме по умолчанию выключаем OCR, чтобы не ждать
    if mode == 'test':
        do_ocr = False
    else:
        ocr_input = input("Добавить OCR для копирования текста? (y/n, Enter = y): ").strip().lower()
        do_ocr = ocr_input not in ('n', 'no', 'н', 'нет', '0')

     # 3. Запускаем нужный режим
    try:
        async with AuthManager() as auth:
            sema = Semaphore(4)

            if mode == 'test':
                url = 'https://urait.ru/viewer/gosudarstvennye-i-municipalnye-finansy-583637'
                await download_single_book(
                    book_url=url, 
                    session=auth.session, 
                    sema=sema, 
                    do_ocr=do_ocr
                )

            elif mode == 'excel':
                # Получаем список ссылок из Excel
                urls = get_spisok()
                if not urls:
                    print("Список ссылок пуст.")
                    return
                
                print(f"В очереди {len(urls)} книг.")
                success = 0
                
                # Проходим по ссылкам по ОДНОЙ
                for i, url in enumerate(urls, 1):
                    print(f"\n[{i}/{len(urls)}] Обработка: {url}")
                    ok = await download_single_book(
                        book_url=url, 
                        session=auth.session, 
                        sema=sema, 
                        do_ocr=do_ocr
                    )
                    if ok:
                        success += 1
                    
                    # Пауза между книгами, чтобы не забанили
                    if i < len(urls):
                        delay = random.uniform(20, 40)
                        print(f"Пауза {delay:.1f} сек перед следующей книгой...")
                        await asyncio.sleep(delay)
                
                print(f"\nИТОГО: Скачано {success} из {len(urls)}")

            else:  # mode == 'single'
                url = input("Введите ссылку на книгу:\n").strip()
                if not url:
                    print("Ссылка не введена!")
                    return
                await download_single_book(url, auth.session, sema, do_ocr)
    except Exception as e:
        print(f"\nОшибка: {e}")
    finally:
        input("\nНажмите Enter для выхода...")

if __name__ == '__main__':
    asyncio.run(main())