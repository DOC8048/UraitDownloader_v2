from pathlib import Path

import pandas as pd

BCODE_PREFIX = 'https://urait.ru/bcode/'
def get_excel_path() -> Path | None:
    """Спрашивает путь к Excel. Возвращает Path или None, если файла нет."""
    raw_path = input(
        "Путь к Excel (Enter — искать Spisok.xlsx в папке Загрузки): "
    ).strip().strip('"')

    if not raw_path:
    # По умолчанию ищем в Загрузках
        excel_path = Path.home() / 'Downloads' / 'Spisok.xlsx'
        print(f"Ищу файл по умолчанию: {excel_path}")
    else:
        excel_path = Path(raw_path)

    if not excel_path.exists():
        print(f"❌ Файл не найден: {excel_path}")
        print("   Положите Spisok.xlsx в папку Загрузки или укажите полный путь.")
        return None

    return excel_path
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
            print("Колонка 'Ознакомиться' не найдена. Вот какие есть:", df.columns.tolist())
    except Exception as e:
        print(f"Не удалось прочитать Excel: {e}")
        return

def get_spisok():
    excel_path = get_excel_path()
    data = batch_download(excel_path=excel_path)
    print (data)
    return data

if __name__ == '__main__':
    get_spisok()

