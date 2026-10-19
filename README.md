# Urait Downloader v2

Скачивалка книг с платформы [urait.ru](https://urait.ru) в PDF с возможностью
поиска и копирования текста (OCR).

Это форк [UraitDownloader](https://github.com/SergeiPopov/UraitDownloader) от SergeiPopov.   
Здесь: умеет скачивать файлы пакетом из выгрузки с Юрайта в Excel , поддержка macOS/Linux, OCR-слой

## <span style="color: red;"> ДИСКЛЕЙМЕР </span>

Проект создан для личного использования — чтобы читать купленные или
доступные по подписке книги в удобном формате. Автор не несёт
ответственности за использование скрипта для нарушения авторских прав
или условий использования платформы urait.ru.

Если вам нужна книга — купите её или оформите подписку на Юрайте.
Скрипт не отменяет необходимость легального доступа.

## Что умеет

- Авторизуется на urait.ru под вашим аккаунтом, сохраняет куки и переиспользует
- Определяет количество страниц из API
- Качает страницы параллельно с ретраями на ошибки
- Собирает всё в один PDF (Авторы + название)
- Пакетное скачивает из Excel
- Накладывает OCR-слой через Tesseract, чтобы текст можно было искать и копировать
- Пишет подробный лог в `urait.log` — для отладки

## Требования

### Python

- Python 3.10 или новее
- Windows / macOS / Linux

### Системные программы (обязательно для OCR)

Для работы OCR-слоя нужно установить три внешние программы. Без них скрипт
сработает, но текст в PDF не будет копироваться.

**Tesseract OCR** — движок распознавания:

- **Windows**: скачать установщик с
  https://github.com/UB-Mannheim/tesseract/wiki. При установке обязательно
  выбрать компонент **Russian language data**.
- **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-rus`
- **macOS**: `brew install tesseract tesseract-lang`

Проверка:
```
tesseract --version
tesseract --list-langs   # должен быть в списке rus
```

**Ghostscript** — обработка PDF:

- **Windows**: скачать с https://www.ghostscript.com/releases/gsdnld.html
  (файл `gs*-w64.exe`, не source). Установщик сам пропишет PATH.
- **Linux**: `sudo apt install ghostscript`
- **macOS**: `brew install ghostscript`

Проверка:
```
gswin64c --version   # Windows
gs --version         # Linux/macOS
```

**QPDF** — ещё одна утилита для PDF:

- **Windows**: скачать с https://qpdf.sourceforge.io/, при установке выбрать
  `Add qpdf to the system PATH for current user`.
- **Linux**: `sudo apt install qpdf`
- **macOS**: `brew install qpdf`

Проверка:
```
qpdf --version
```

## Установка

1. Клонировать репозиторий:
   ```
   git clone https://github.com/DOC8048/urait-downloader.git
   cd urait-downloader
   ```

2. Создать виртуальное окружение и установить зависимости:
   ```
   python -m venv venv
   venv\Scripts\activate          # Windows
   source venv/bin/activate       # Linux/macOS
   pip install -r requirements.txt
   ```
3. Для запуска приложения необходимо скопировать `account.example.txt` 
   в `account.txt`:
   ```bash
   cp account.example.txt account.txt   # Linux/macOS
   copy account.example.txt account.txt # Windows
   ```
   Содержимое файла `account.example.txt` : 

      ```
      URAIT_EMAIL=you_email@gmail.com
      URAIT_PASSWORD=your_password 
      ```

   И вписать свои данные, это необходимо, потому что только авторизованные пользователи могу просматривать всё содержимое книги 
   Данные хранятся локально в файле account.txt и используются только для авторизации на urait.ru.
 
4. Убедиться, что все три системные программы (Tesseract, Ghostscript, QPDF)
   установлены и доступны из PATH.

## Использование

```
python main_router.py
```

Программа спросит:

1. **Ссылку на книгу** — можно вставлять как `https://urait.ru/bcode/...` , так
   и `https://urait.ru/viewer/...`. Оба формата работают. По умолчанию скачивает по ссылке 

2. **Пакетное скачивание из  Excel** — Пройдется по ссылкам в  Excel и скачает все книги 
   (также под OCR если выбрали) файл вида **Spisok.xlsx**. Программа возьмет файл из папки *загрузки* или по пути переданной в терминал, также можно положить файл в папку. Файл должен точно соответствовать такому названию: **Spisok** c расширением **.xlsx**

3. **Нужен ли OCR** — по умолчанию да. Если нажмёшь `n`, скачается PDF без
   текстового слоя (быстрее).

Дальше программа всё сделает сама: скачает страницы, соберёт PDF, наложит
OCR-слой. Готовый файл появится в той же папке.

## Логи

Все технические сообщения (статусы запросов, ошибки страниц, детали OCR)
пишутся в `urait.log`. Если что-то пошло не так — сначала смотри туда.

## Известные ограничения

- **Tesseract, Ghostscript и QPDF должны быть установлены отдельно.**
  PyInstaller-сборка не упаковывает их в exe, потому что это внешние
  программы, а не Python-модули.
- **Работает только с книгами, к которым у вас есть легальный доступ.**
  Скрипт использует ваш аккаунт Юрайта и те же запросы, что и просмотрщик
  книг в браузере.
- **Не для массового скачивания.** Скрипт рассчитан на скачивание книг по
  одной. Если нужно много — делайте паузы между запусками, чтобы не
  привлекать внимание сервера.

## Благодарности

- [Оригинальный проект](https://github.com/SergeiPopov/UraitDownloader)
- Сообществу Tesseract OCR, Ghostscript, PyMuPDF и QPDF — за инструменты

## Планы

- [] Собрать exe через PyInstaller
- [x] Поддержка пакетного скачивания из Excel
- [] Собрать полноценное приложение 
- [] Опционально: пропуск SVG-файлов на диске (конвертация из памяти)

