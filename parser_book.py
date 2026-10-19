import asyncio
import os
import re
import shutil
import tempfile
from random import uniform

import aiofiles
import pymupdf
from aiohttp import ClientTimeout
from pypdf import PdfWriter

from login import logger

url = 'https://urait.ru/bcode/588546'
url2 = "https://urait.ru/viewer/finansy-588546#page/1"
CONTENTS_URL = 'https://urait.ru/api/contents/{book_id}'
VIEWER_DATA_URL = 'https://urait.ru/viewer/data/{book_uuid}/{page}'
VIEWER_PAGE_URL = 'https://urait.ru/viewer/page/{book_uuid}/{page}'
LANG_OCR = 'rus+eng'
LOG = 'Logi_debag'
PAGE_TIMEOUT = ClientTimeout(total=30)
def parse_viewer_url(url: str) -> str:
    """Извлекает id книги из ссылки на просмотр.

    Args:
        url: Ссылка вида https://urait.ru/viewer/<slug>-<id>[#page/N].

    Returns:
        Числовой id книги.

    Raises:
        ValueError: в ссылке нет числового id.
    """
    slug = url.removeprefix('https://urait.ru/viewer/').split('#')[0].split('/')[0]
    match = re.search(r'-(\d+)$', slug)
    if not match:
        raise ValueError(f'В ссылке просмотра нет id книги: {url}')
    return match.group(1)

def parse_bcode_url(url: str) -> str:
    """Извлекает id книги из ссылки на карточку учебника.

    Args:
        url: Ссылка вида https://urait.ru/bcode/<id>.

    Returns:
        Числовой id книги.

    Raises:
        ValueError: в ссылке нет числового id.
    """
    slug = url.removeprefix('https://urait.ru/bcode/').strip('/')
    match = re.fullmatch(r'(\d+)', slug)
    if not match:
        raise ValueError(f'В ссылке карточки нет id книги: {url}')
    return match.group(1)

def extract_book_id(url: str) -> str:
    """Роутер: выбирает метод парсинга id по виду пользовательской ссылки.

    Args:
        url: Ссылка вида https://urait.ru/bcode/<id> или https://urait.ru/viewer/<slug>-<id>.

    Returns:
        Числовой id книги.

    Raises:
        ValueError: ссылка не распознана.
    """
    clean = url.strip()
    for prefix, parser in URL_PARSERS:
        if clean.startswith(prefix):
            return parser(clean)
    raise ValueError(f'Неизвестный тип ссылки: {url}')

URL_PARSERS = (
    ('https://urait.ru/bcode/', parse_bcode_url),
    ('https://urait.ru/viewer/', parse_viewer_url),
)
async def parse_book_info(book_id: str, client) -> dict:
    """Запрашивает содержимое книги в API и возвращает блок data.

    Raises:
        RuntimeError: сервер вернул ошибку или в ответе нет data.
    """
    response = await client.get(CONTENTS_URL.format(book_id=book_id))
    if response.status != 200:
        raise RuntimeError(f'API вернул HTTP {response.status} для книги {book_id}')
    body = await response.json()
    data = body.get('data')
    if not isinstance(data, dict):
        raise RuntimeError(f'В ответе API нет data для книги {book_id}')
    # UUID книги
    book_uuid = data.get('id')
    # Название
    title = data.get('title')
    # Авторы
    authors = data.get('authors_short')
    print(f'Название: {title}')
    print(f'UUID: {book_uuid}')
    print(f'Авторы:{authors}')
    return {'book_code': book_uuid, 'book_title': title, 'authors':authors}

async def get_page_count(book_uuid: str, client) -> int:
    """Запрашивает данные первой страницы просмотра книги и возвращает JSON.

    Raises:
        RuntimeError: сервер вернул ошибку или не-JSON данные.
    """
    response = await client.get(VIEWER_DATA_URL.format(book_uuid=book_uuid, page=1))
    if response.status != 200:
        raise RuntimeError(f'API просмотра вернул HTTP {response.status} для книги {book_uuid}')
    data = await response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f'В ответе API просмотра нет данных для книги {book_uuid}')
    page_count = data.get('page_count') 
    if not isinstance(page_count, int):
            raise RuntimeError(f'В ответе API просмотра нет page_count для книги {book_uuid}')
    return page_count

async def page_exists(client, book_uuid: str, page: int) -> bool:
    """Проверяет, существует ли страница."""
    try:
        r = await client.get(VIEWER_DATA_URL.format(book_uuid=book_uuid, page=page), timeout=PAGE_TIMEOUT)
        if r.status != 200:
            return False
        text = await r.text()
        return '<svg' in text[:500]
    except Exception:
        return False

async def parse_page(
        pdf_stack: list,
        book_code: str, 
        page: int,
        session, 
        semaphore: asyncio.Semaphore,
        )-> None:
        """ Парсит pdf, превращая svg в pdf"""
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
                with pymupdf.open(svg_file_name) as svg_doc:
                    pdf_bytes = svg_doc.convert_to_pdf()
                with pymupdf.open('pdf',pdf_bytes) as pdf_doc:
                    pdf_doc.save(pdf_file_name)
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
    """Создаем pdf-файл"""
    pdf_stack.sort()
    with PdfWriter() as merger:
        for pdf in pdf_stack:
            merger.append(f'./temp/{pdf}.pdf')
        merger.write(f"{file_name}.pdf")
    return f"{file_name}.pdf"

def add_ocr_layer(pdf_path: str, language: str = LANG_OCR):
    """Накладывает  OCR-слой на pdf-файл(без OCR), заменяя его в итоге получая pdf-файл с OCR"""
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


