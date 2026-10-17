import asyncio
import shutil
import sys
from asyncio import Semaphore

import environ

from login import AuthManager, logger

# from main_new import DEFAULT_HEADERS
from parser_book import (
    add_ocr_layer,
    create_pdf,
    find_total_pages,
    parse_book_info,
    parse_page,
    process,
)

book_url_test = 'https://urait.ru/viewer/gosudarstvennye-i-municipalnye-finansy-583637'
env = environ.Env()
environ.Env.read_env('account.txt')
EMAIL = env('URAIT_EMAIL')
PASSWORD = env('URAIT_PASSWORD')
if not  (EMAIL and PASSWORD):
    raise SystemExit(
    "account.txt не настроен.\n"
    "Классика: склонировал репо, запустил, не читая README. \n"
    "Как исправить:\n"
    "  1. Скопируй account.example.txt в account.txt\n"
    "  2. Впиши туда свой email и пароль от urait.ru\n"
    "  3. Запусти скрипт ещё раз\n"
)
DEFAULT_HEADERS = {
    'Host': 'urait.ru',
    'Origin': 'https://urait.ru',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36'
}
async def main():
    pdf_stack = []
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        book_url = 'https://urait.ru/viewer/gosudarstvennye-i-municipalnye-finansy-583637'
        print(f"[TEST MODE] Использую тестовую книгу: {book_url}")
    else: 
        book_url = input("Введите ссылку на книгу (пример - https://urait.ru/book/...) или https://urait.ru/viewer/...)\n").strip()
        if not book_url:
            print('Ссылка не введена!')
            return
    pages_input = input("Введите количество страниц (Enter — определить автоматически):\n").strip()
    known_pages = int(pages_input) if pages_input.isdigit() else None
    ocr_input = input("Добавить OCR для копирования текста? (y/n, Enter = y): ").strip().lower()
    do_ocr = ocr_input != 'n'
    try:
        sema = Semaphore(2)
        async with AuthManager() as auth:
            print('Авторизация прошла успешно')
            book_info = await parse_book_info(book_url= book_url, session=auth.session, semaphore=sema)
            print("Ищу книгу...")
            if known_pages:
                total_pages = known_pages
                print(f'Использую введённое количество: {total_pages}')
            else:
                print("Определяю количество страниц...")
                total_pages = await find_total_pages(session=auth.session, book_code= book_info['book_code'])
            print(f"Начинаю скачивание {total_pages} страниц...") 
            # print(f'Всего страниц {total_pages}')   
            tasks = [
                asyncio.create_task(
                    parse_page(pdf_stack=pdf_stack, book_code= book_info['book_code'], page=p, session=auth.session, semaphore= sema)
                )
                for p in range(1, total_pages + 1)
            ]
            task_proc = asyncio.create_task(process(pdf_stack=pdf_stack, total_pages=total_pages,tasks=tasks))
            await asyncio.gather(*tasks, task_proc)
            print("Собираю PDF...")
            # Собираем автора и название книги 
            pdf_name = f"{book_info['authors']} {book_info['book_title']}"
            pdf_file = create_pdf(pdf_name, pdf_stack)
            print(f"PDF готов: {book_info['authors']} {book_info['book_title']}.pdf")
            # ==========================
            # Обработка ocr
            # ====================================
            if do_ocr:
                print("\nРаспознаю текст (OCR). Это может занять несколько минут...")
                try:
                    await asyncio.to_thread(add_ocr_layer, pdf_file)
                    print("Текстовый слой добавлен — текст можно копировать.")
                except Exception as e:
                    print(f"OCR не удался: {e}")
                    print("PDF сохранён без текстового слоя. Подробности в urait.log.")
            else:
                print("OCR пропущен.")
            
            print(f"\nГотово! {pdf_file}")
            # notify("Книга скачана", book_info['book_title'])
    except Exception as e:
        logger.exception('Ошибка работы программы')
        print(f"\nЧто-то пошло не так: {e}")
        print("Подробности в файле LOG_FILE")
    finally:
            try:
                shutil.rmtree('./temp')
            except Exception:  # noqa: S110
                pass
            input("\nНажмите Enter для выхода...")

if __name__ == '__main__':
    asyncio.run(main())



