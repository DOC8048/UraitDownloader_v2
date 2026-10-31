from pathlib import Path  # noqa: N999

from backend.utilits_excel.download_excel import batch_download


def get_excel_path_CLI() -> Path | None:
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

def get_spisok_CLI():
    excel_path = get_excel_path_CLI()
    if not excel_path:
        print("Ошибка: не удалось получить путь к файлу Excel.")
        return []
    
    data = batch_download(excel_path=excel_path)
    if not data:
        print("В Excel не найдено ссылок.")
        return []
    
    print(f"Найдено ссылок: {len(data)}")
    
    return data

if __name__ == '__main__':
    urls = get_spisok_CLI()
    print(urls)

