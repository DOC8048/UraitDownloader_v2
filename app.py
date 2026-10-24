
import asyncio
import multiprocessing
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser

import customtkinter as ctk

from back import run_download_process


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Титульник
        self.geometry(f"{700}x{600}")
        self.title("Urait Downloader") 

        # проверка на начилие пакетов для OCR
        self.deps_status = self.check_dependencies()

        # Кнопка слайдбара
        has_errors = any(not status[0] for status in self.deps_status.values())
        btn_text = "❌ Проблемы с зависимостями (нажми чтобы раскрыть)" if has_errors else "✅ Все зависимости установлены"
        btn_color = "#8B0000" if has_errors else "#2b2b2b" # Темно-красный если ошибка, темно-серый если ок

        self.btn_toggle_deps = ctk.CTkButton(
            self, 
            text=btn_text, 
            fg_color=btn_color,
            command=self.toggle_deps_panel
        )

        self.btn_toggle_deps.pack(pady=(10, 0), padx=20, fill="x")

        self.frame_deps = ctk.CTkFrame(self, fg_color="#1e1e1e")
        self.is_deps_visible = False # Флаг состояния
        self._build_deps_content()
        # Если есть ошибки — сразу открываем панель при запуске
        if has_errors:
            self.toggle_deps_panel()

        # Поле ввода   
        self.entry_url = ctk.CTkEntry(self, width=400, placeholder_text="Вставь ссылку сюда")
        self.entry_url.pack(pady=20)

        # Вставка из буфера
        self.enable_clipboard_support(self.entry_url)

        # свитч OCR
        self.checkbox_ocr = ctk.CTkSwitch(self, text="Добавить OCR (распознать текст)", onvalue=True, offvalue=False)
        self.checkbox_ocr.deselect() # По умолчанию включено
        self.checkbox_ocr.pack(anchor="w", pady=10, padx=10)

        # свитч excel
        self.checkbox_excel = ctk.CTkSwitch(self, text="Пакетное скачивание", onvalue=True, offvalue=False)
        self.checkbox_excel.deselect() # По умолчанию выключено
        self.checkbox_excel.pack(anchor="w", pady=10, padx=10)

        # кнопка скачки
        self.btn_download = ctk.CTkButton(self, text="Скачать", command=self.start_download_thread)
        self.btn_download.pack(pady=10)

        # Лог
        self.textbox = ctk.CTkTextbox(self, width=600, height=300)
        self.textbox.pack(pady=20)

    def log(self, message):
        """Добавляет текст в лог"""
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")
    def start_download_thread(self):
        """Запускает скачивание в фоне, чтобы окно не зависло""" 
        # 1. Собираем данные из интерфейса
        url = self.entry_url.get().strip()
        mode = 'excel' if bool(self.checkbox_excel.get()) else 'single'
        do_ocr = bool(self.checkbox_ocr.get())
        if not url:
            self.log("Ошибка: введи ссылку!")
            return
        
        # Блокируем кнопку и очищаем лог
        self.btn_download.configure(state="disabled", text="Скачиваю...")
        self.textbox.delete("1.0", "end")
        
        # Запускаем поток
        thread = threading.Thread(target=self.run_backend, args=(mode, url, do_ocr))
        thread.daemon = True
        thread.start()


    def check_dependencies(self):
        """Возвращает словарь {название: (найден ли, ссылка на скачивание)}"""
        deps = {
            "Tesseract": ("tesseract", "https://github.com/UB-Mannheim/tesseract/wiki"),
            "Ghostscript": ("gswin64c", "https://www.ghostscript.com/releases/gsdnld.html"),
            "QPDF": ("qpdf", "https://qpdf.sourceforge.io/")
            }
    
        results = {}
        for name, (cmd, url) in deps.items():
            try:
                # Пытаемся запустить команду с флагом версии
                subprocess.run([cmd, "--version"], capture_output=True, check=True, timeout=5)
                results[name] = (True, url) # True = найден
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                results[name] = (False, url) # False = не найден

        return results

    def toggle_deps_panel(self):
        """Открывает или закрывает панель с зависимостями."""
        if self.is_deps_visible:
            self.frame_deps.pack_forget() # Скрыть
            self.is_deps_visible = False
        else:
            # Показать панель под кнопкой
            self.frame_deps.pack(pady=(5, 0), padx=20, fill="x", after=self.btn_toggle_deps)
            self.is_deps_visible = True

    def _build_deps_content(self):
        """Наполняет панель строками с проверками."""
        label_title = ctk.CTkLabel(
            self.frame_deps, 
            text="Системные программы (нужны для OCR):", 
            font=("Arial", 13, "bold"),
            text_color="#aaaaaa"
        )
        label_title.pack(anchor="w", padx=10, pady=(10, 5))

        for dep_name, (is_installed, download_url) in self.deps_status.items():
            row = ctk.CTkFrame(self.frame_deps, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            
            status_text = f"✅ {dep_name}" if is_installed else f"❌ {dep_name} не найден"
            color = "#4CAF50" if is_installed else "#F44336" # Более приятные цвета
            
            lbl = ctk.CTkLabel(row, text=status_text, text_color=color, width=250, anchor="w")
            lbl.pack(side="left")
            
            if not is_installed:
                btn = ctk.CTkButton(
                    row, text="Скачать", width=80, height=24, 
                    fg_color="#F44336", hover_color="#D32F2F",
                    command=lambda url=download_url: webbrowser.open(url)
                )
                btn.pack(side="left", padx=10)

    def enable_clipboard_support(self, widget):
        """Добавляет горячие клавиши и контекстное меню для виджета."""
        
        # 1. Привязываем горячие клавиши (Windows/Linux)
        widget.bind("<Control-v>", lambda e: self.paste_text(widget))
        widget.bind("<Control-V>", lambda e: self.paste_text(widget))
        
        # Для macOS (Command вместо Control)
        widget.bind("<Command-v>", lambda e: self.paste_text(widget))
        widget.bind("<Command-V>", lambda e: self.paste_text(widget))

        # 2. Создаем контекстное меню для правой кнопки мыши
        def show_context_menu(event):
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Вставить", command=lambda: self.paste_text(widget))
            menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
            menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
            menu.tk_popup(event.x_root, event.y_root)

        # Button-3 = правая кнопка мыши для Windows/Linux, Button-2 = для macOS
        widget.bind("<Button-3>", show_context_menu)
        widget.bind("<Button-2>", show_context_menu)

    def paste_text(self, widget):
        """Читает текст из буфера и вставляет его в виджет."""
        try:
            text = widget.clipboard_get()
            widget.insert(widget.index("insert"), text)
        except tk.TclError:
            pass # Если буфер пуст, просто ничего не делаем

    def run_backend(self,mode, url, do_ocr):
        """Вызываем бэкенд"""
        old_stdout = sys.stdout
        sys.stdout = self

        async def task():
            try:
                await run_download_process(
                    mode=mode,
                    url=url,
                    do_ocr=do_ocr)
            except Exception as e:
                self.log(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
            finally:
                # Разблокируем кнопку (через after, т.к. мы в другом потоке)
                self.after(0, 
                    lambda: self.btn_download.configure(
                        state="normal", 
                        text="Скачать"
                    )
                )
        try:
            asyncio.run(task())
        finally:
            sys.stdout = old_stdout
            
     # --- Методы для перехвата print() ---
    def write(self, text):
        if '\r' in text:
            clean_text = text.split('\r')[-1]
            if clean_text:
                self.textbox.delete("end-2l", "end-1c")
                self.textbox.insert("end", clean_text + "\n")
                self.textbox.see("end")
        else: 
            if text.strip():
                self.log(text.strip())

    def flush(self):
        pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = App()
    app.mainloop()

