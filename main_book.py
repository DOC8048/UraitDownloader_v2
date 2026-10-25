
import asyncio
import shutil
from asyncio import Semaphore

from login import LOG, logger
from parser_book import (
    add_ocr_layer,
    create_pdf,
    extract_book_id,
    get_page_count,
    parse_book_info,
    parse_page,
    process,
)


async def download_single_book(book_url, session, sema: Semaphore, do_ocr: bool) -> bool:
    """Скачивает одну книгу. Возвращает True, если успешно."""
    try:
        book_id = extract_book_id(url=book_url)
        book_info = await parse_book_info(book_id=book_id,client=session)
        print("Определяю количество страниц...")
        total_pages = await get_page_count(book_uuid=book_info['book_code'],client=session)
        print(f"Начинаю скачивание {total_pages} страниц...") 
        pdf_stack = []
        tasks = [
            asyncio.create_task(
                parse_page(pdf_stack=pdf_stack, book_code= book_info['book_code'], page=p, session=session, semaphore= sema)
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
        return True
    except Exception as e:
        logger.exception('Ошибка работы программы')
        print(f"\nЧто-то пошло не так: {e}")
        print(f"Подробности в файле{LOG}" )
        return False
    finally:
        shutil.rmtree('./temp')
