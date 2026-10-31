from pathlib import Path

from backend.utilits_excel.download_excel import batch_download


def get_excel_path_GUI():
    """Ищет Excel в загрузках, функция для взаимодействия с GUI"""
    excel_path = Path.home() / 'Downloads' / 'Spisok.xlsx'
    print(f"Ищу файл по умолчанию: {excel_path}")
    if not excel_path.exists():
        print(f"❌ Файл не найден: {excel_path}")
        print("   Положите Spisok.xlsx в папку Загрузки или укажите полный путь.")
        return None
    return excel_path 

def get_spisok_GUI():
    excel_path = get_excel_path_GUI()
    if not excel_path:
       print("Ошибка: не удалось получить путь к файлу Excel.")
       return[] 
    data = batch_download(excel_path=excel_path)
    if not data :
        print("В Excel не найдено ссылок.")
        return [] 
    print(f"Найдено ссылок: {len(data)}") # Прерываем, если файл не найден
    return data

if __name__ == '__main__':
    urls = get_spisok_GUI()
    print(urls)