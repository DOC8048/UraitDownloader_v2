
import asyncio
import os
import re
import shutil
import tempfile
from asyncio import Semaphore
from random import uniform

import aiofiles
import pymupdf
from aiohttp import ClientSession, ClientTimeout
from pypdf import PdfWriter

from login import logger

LANG_OCR = 'rus+eng'
LOG_FILE = 'urait.log'
TEMP_DIR = 'temp'
PAGE_TIMEOUT = ClientTimeout(total=30)
async def parse_book_info(book_url: str, session, semaphore: Semaphore):
    """Ищем информацию по книге. Возвращает словарь:
        book_code: UUID книги,
        book_title: название книги,
        authors: авторы/авторов  
    """
    async with semaphore:
        print("Получение информации о книге...")
        # Подготовка ссылки
        if '/viewer/' in book_url:
            viewer_url = book_url
        else: 
            viewer_url = book_url.replace('/book/','/viewer/') 
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
        # Ищем автора
        fd = await session.get(f"https://urait.ru/course/{book_code}?utm_source=biblioonline_share")
        course_html = await fd.text()
        title_course = re.search(r'<title>(.*?)</title>', course_html, re.DOTALL)
        if not title_course:
            authors = ''
        else:
            raw_title = title_course.group(1)
            if '—' in raw_title:
                raw_title = raw_title.split('—')[0].strip()
            author_pattern = r'[А-ЯЁ][а-яё\-]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.'
            authors_list = re.findall(author_pattern, raw_title)
            authors = ', '.join(authors_list)

    # Чистим название от запрещённых символов для Windows
    book_title = re.sub(r'[<>:"/\\|?*]', '_', book_title).strip()[:150]
    if not book_title:
        book_title = 'book'
        
    print(f'Название: {book_title}')
    print(f'UUID: {book_code}')
    print(f'Авторы:{authors}')
    return {'book_code': book_code, 'book_title': book_title, 'authors':authors}

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

async def find_total_pages(session, book_code: str) -> int:
    """Бинарный поиск последней существующей страницы."""
    print("Определение количества страниц...")
    if not await page_exists(session, book_code, page=1):
        raise ValueError("Страница 1 не существует. Проблемы с доступом к книге?")

    # Ищем верхнюю границу
    lo = 1
    hi = 2
    while await page_exists(session, book_code, page=hi):
        lo = hi
        hi *= 2
        if hi > 20000:  # защита от бесконечного цикла
            break

    # Бинарный поиск между lo и hi
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if await page_exists(session, book_code, page= mid):
            lo = mid
        else:
            hi = mid

    logger.info(f'Всего страниц: {lo}')
    return lo

async def parse_page(
        pdf_stack: list,
        book_code: str, 
        page: int,
        session, 
        semaphore: Semaphore,
        ):
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

async def process(pdf_stack: list, total_pages, tasks: list):
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
    """Накладывает  OCR-слой на pdf-файл(без OCR), замененяя его в итоге получая pdf-файл с OCR"""
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