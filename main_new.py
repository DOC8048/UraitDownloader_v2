import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile
from asyncio import Semaphore
from random import uniform

import aiofiles
import environ
import pymupdf
from aiohttp import ClientSession, ClientTimeout
from pypdf import PdfWriter

env = environ.Env()
LANG_OCR = 'rus+eng'
LOG_FILE = 'urait.log'
TEMP_DIR = 'temp' # хз пока зачем(убрать)
environ.Env.read_env('account.txt')
EMAIL = env('URAIT_EMAIL')
PASSWORD = env('URAIT_PASSWORD')
assert EMAIL and PASSWORD, "Укажите данные от аккаунта ЮРАЙТ в файле account.txt"

DEFAULT_HEADERS = {
    'Host': 'urait.ru',
    'Origin': 'https://urait.ru',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='w'),
    ]
)
logger = logging.getLogger(__name__)
PAGE_TIMEOUT = ClientTimeout(total=30) 
# --- Кроссплатформенные уведомления ---
def notify(title: str, message: str):
    try:
        if os.name == 'nt':
            from win11toast import toast
            toast(message, title=title)
        elif sys.platform == 'darwin':
            os.system(f'osascript -e \'display notification "{message}" with title "{title}"\'')
        else:
            os.system(f'notify-send "{title}" "{message}"')
    except Exception as e:
        logger.warning(f'Не удалось показать уведомление: {e}')

async def login(session: ClientSession, semaphore: Semaphore):
    print("Авторизация пользователя...")
    async with semaphore:
        response = await session.post(
            'https://urait.ru/login',
            json={'email': EMAIL, 'password': PASSWORD},
            allow_redirects=True
        )
        text = await response.text()
        assert 'Пользователь с указанным логином не зарегистрирован' not in text, \
            f"Нет пользователя в системе {EMAIL}"
        assert 'Неверный пароль' not in text, f"Неверный пароль для пользователя {EMAIL}"
        print('Авторизация прошла успешно')


async def parse_book_info(book_url: str, session: ClientSession, semaphore: Semaphore) -> dict:
    async with semaphore:
        print("Получение информации о книге...")
        if '/viewer/' in book_url:
            viewer_url = book_url
        else: 
            viewer_url = book_url.replace('/book/','/viewer/') 
        # viewer_url = book_url.replace('/book/', '/viewer/') проверим на работоспрособность, потом удалить
        response = await session.get(viewer_url)
        text = await response.text()

        # UUID книги из new Viewer('...')
        m = re.search(r"new Viewer\('([^']+)'", text)
        if not m:
            raise ValueError("Не удалось извлечь UUID книги. Проверь ссылку.")
        book_code = m.group(1)

        # Название — берём из <title> или h1
        title_match = re.search(r'<title>(.*?)</title>', text, re.DOTALL)
        if title_match:
            book_title = title_match.group(1).split('—')[0].split('–')[0].strip()
        else:
            book_title = 'book'

        # Чистим название от запрещённых символов для Windows
        book_title = re.sub(r'[<>:"/\\|?*]', '_', book_title).strip()[:150]
        if not book_title:
            book_title = 'book'

        print(f'Название: {book_title}')
        print(f'UUID: {book_code}')
        return {'book_code': book_code, 'book_title': book_title}


async def page_exists(session: ClientSession, book_code: str, page: int) -> bool:
    """Проверяет, существует ли страница."""
    url = f'https://urait.ru/viewer/page/{book_code}/{page}'
    try:
        r = await session.get(url, timeout=PAGE_TIMEOUT)
        if r.status != 200:
            return False
        text = await r.text()
        return '<svg' in text[:500]
    except Exception:
        return False


async def find_total_pages(session: ClientSession, book_code: str) -> int:
    """Бинарный поиск последней существующей страницы."""
    print("Определение количества страниц...")
    if not await page_exists(session, book_code, 1):
        raise ValueError("Страница 1 не существует. Проблемы с доступом к книге?")

    # Ищем верхнюю границу
    lo = 1
    hi = 2
    while await page_exists(session, book_code, hi):
        lo = hi
        hi *= 2
        if hi > 20000:  # защита от бесконечного цикла
            break

    # Бинарный поиск между lo и hi
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if await page_exists(session, book_code, mid):
            lo = mid
        else:
            hi = mid

    print(f'Всего страниц: {lo}')
    return lo


async def parse_page(pdf_stack: list, 
                     book_code: str, 
                     page: int,
                     session: ClientSession, 
                     semaphore: Semaphore,
                        ):
        try:
            async with semaphore:
                # Небольшая случайная задержка — чтобы не долбить сервер ровным потоком
                await asyncio.sleep(uniform(0.03, 0.12))
                response = await session.get(
                    f'https://urait.ru/viewer/page/{book_code}/{page}',
                    timeout=PAGE_TIMEOUT
                )
                if response.status != 200:
                    logger.warning(f'Стр. {page}: статус {response.status}, пропускаю')
                    return

                svg_file_name = f'temp/{page}.svg'
                pdf_file_name = f'temp/{page}.pdf'
                os.makedirs(os.path.dirname(svg_file_name), exist_ok=True)
                async with aiofiles.open(svg_file_name, 'w', encoding='utf-8') as file:
                    await file.write(await response.text())

            try:
                svg_doc = pymupdf.open(svg_file_name)
                pdf_bytes = svg_doc.convert_to_pdf()
                svg_doc.close()

                pdf_doc = pymupdf.open('pdf', pdf_bytes)
                pdf_doc.save(pdf_file_name)
                pdf_doc.close()
            except Exception as e:
                logger.warning(f'Стр. {page}: ошибка конвертации SVG->PDF: {e}')
                return
            pdf_stack.append(page)
        except Exception as e:
            print(f'Не удалось получить стр. {page}: {e}')

async def process(pdf_stack: list, total_pages: int, tasks: list):
    """ Процесс счета страниц"""
    while True:
        if all(t.done() for t in tasks):
            print()
            print(f"Скачивание завершено. Успешно: {len(pdf_stack)} из {total_pages}")
            break
        proc_str = f"\rСкачано {len(pdf_stack):04d} из {total_pages:04d}"
        print(proc_str, end='', flush=True)
        await asyncio.sleep(1)

def create_pdf(file_name: str, pdf_stack: list):
    pdf_stack.sort()
    merger = PdfWriter()
    for pdf in pdf_stack:
        merger.append(f'./temp/{pdf}.pdf')
    merger.write(f"{file_name}.pdf")
    merger.close()

def add_ocr_layer(pdf_path: str, language: str = LANG_OCR):
    import ocrmypdf

    logger.info(f"Запуск OCR для: {pdf_path}")
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        ocrmypdf.ocr(
            pdf_path,
            tmp_path,
            language=language,
            force_ocr=True,       # не трогаем страницы, где уже есть текст
            jobs=os.cpu_count(),  # параллельно по числу ядер
            deskew=False,
            clean=False,
            optimize=0,
        )
        shutil.move(tmp_path, pdf_path)
        logger.info("OCR успешно завершён")
    except Exception as e:
        logger.error(f"Ошибка OCR: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    
async def main():
    pdf_stack = []
    book_url = input("Введите ссылку на книгу (пример - https://urait.ru/book/...)\n").strip()

    pages_input = input(
        "Введите количество страниц (Enter — определить автоматически):\n"
    ).strip()
    known_pages = int(pages_input) if pages_input.isdigit() else None

    ocr_input = input("Добавить OCR для копирования текста? (y/n, Enter = y): ").strip().lower()
    do_ocr = ocr_input != 'n'

    try:
        semaphore = Semaphore(4)
        async with ClientSession(headers=DEFAULT_HEADERS) as session:
            print("\nАвторизуюсь...")
            await login(session, semaphore)
            book_info = await parse_book_info(book_url, session, semaphore)
            print("Ищу книгу...")

            if known_pages:
                total_pages = known_pages
                print(f'Использую введённое количество: {total_pages}')
            else:
                print("Определяю количество страниц...")
                total_pages = await find_total_pages(session, book_info['book_code'])

            print(f"Начинаю скачивание {total_pages} страниц...")
            tasks = [
                asyncio.create_task(
                    parse_page(pdf_stack, book_info['book_code'], p, session, semaphore)
                )
                for p in range(1, total_pages + 1)
            ]
            task_proc = asyncio.create_task(process(pdf_stack, total_pages,tasks))
            await asyncio.gather(*tasks, task_proc)
            print("Собираю PDF...")
            create_pdf(book_info['book_title'], pdf_stack)
            pdf_file = f"{book_info['book_title']}.pdf"
            print(f"PDF готов: {book_info['book_title']}.pdf")
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
            notify("Книга скачана", book_info['book_title'])

    except Exception as e:
        logger.exception('Ошибка работы программы')
        print(f"\nЧто-то пошло не так: {e}")
        print(f"Подробности в файле {LOG_FILE}")

    finally:
        try:
            shutil.rmtree(f'./{TEMP_DIR}')
        except Exception:  # noqa: S110
            pass
        input("\nНажмите Enter для выхода...")


if __name__ == '__main__':
    asyncio.run(main())
