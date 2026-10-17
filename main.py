
import asyncio
import shutil
import sys
from asyncio import Semaphore

from debag import (
    add_ocr_layer,
    create_pdf,
    extract_book_id,
    get_page_count,
    parse_book_info,
    parse_page,
    process,
)
from login import AuthManager, logger


async def main():
    pdf_stack = []
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        book_url = 'https://urait.ru/viewer/gosudarstvennye-i-municipalnye-finansy-583637'
        print(f"[TEST MODE] Использую тестовую книгу: {book_url}")
    else: 
        book_url = input("Введите ссылку на книгу (пример - https://urait.ru/bcode/) или https://urait.ru/viewer/...)\n").strip()
        if not book_url:
            print('Ссылка не введена!')
            return
    ocr_input = input("Добавить OCR для копирования текста? (y/n, Enter = y): ").strip().lower()
    do_ocr = ocr_input not in ('n', 'no', 'н', 'нет', '0')
    print(f"[DEBUG] Введено: '{ocr_input}', OCR включен: {do_ocr}")
    try:
        sema = Semaphore(4)
        book_id = extract_book_id(url=book_url)
        async with AuthManager() as auth:
            print('Авторизация прошла успешно')
            print("Ищу книгу...")
            book_info = await parse_book_info(book_id=book_id,client=auth.session)
            print("Определяю количество страниц...")
            total_pages = await get_page_count(book_uuid=book_info['book_code'],client=auth.session)
            print(f"Начинаю скачивание {total_pages} страниц...") 
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