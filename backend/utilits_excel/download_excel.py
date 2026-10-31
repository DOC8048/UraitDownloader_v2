import pandas as pd

from backend.logger import logger


def batch_download(excel_path):
    """Скачивает все книги из Excel-файла."""
    print(f"Читаю файл: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path,header=3)
        df.columns = df.columns.str.strip()
        # Теперь ищем нужную колонку
        if 'Ознакомиться' in df.columns:
            urls = df['Ознакомиться'].dropna().tolist()
            clean_url=[url.strip().replace('/author-course/', '/viewer/') for url in urls]
            # data = {url: False for url in urls}
            return clean_url
        else:
            logger.warning("Колонка 'Ознакомиться' не найдена. Вот какие есть:", df.columns.tolist())
    except Exception as e:
        print(f"Не удалось прочитать Excel: {e}")
        return