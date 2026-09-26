# -*- coding: utf-8 -*-
"""Окно оператора.

Рабочая версия для цеха. Только чтение: утилита разбирает копии текстовых
файлов и ничего не пишет ни в программы, ни в стойку станка.

Модуль намеренно тонкий. Отбор, состав колонок и выгрузка живут в
presentation, расчёт — в core, поэтому проверяются тестами без поднятия окна.
Здесь остаются только размещение элементов и реакция на действия оператора.

Цель сборки — Windows 7 32-bit, Python 3.8.10: tkinter из стандартной
библиотеки, никаких внешних зависимостей.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from . import presentation
from .core import balance
from .core.model import PartStatus, ShiftSummary
from .core.syntax import DEFAULT_SYNTAX

TITLE = 'Учёт готовности деталей'

# Экран у стойки смотрят стоя и не вплотную — шрифт крупнее обычного.
FONT = ('Segoe UI', 10)
FONT_BOLD = ('Segoe UI', 10, 'bold')
FONT_BIG = ('Segoe UI', 11)

COLOR_DONE_BG = '#d8f0d8'
COLOR_DONE_FG = '#14521a'
COLOR_OK = '#14521a'
COLOR_WARN = '#8a4b00'
COLOR_ERROR = '#8a1c1c'
COLOR_MUTED = '#555555'

COLUMN_WIDTHS = (170, 120, 100, 120, 100)
COLUMN_ANCHORS = ('w', 'e', 'e', 'e', 'center')


def _enable_dpi_awareness():
    """Чёткий текст при масштабировании экрана.

    На Windows 8.1 и новее есть shcore, на Windows 7 — только user32.
    Неудача не важна: окно просто будет как раньше.
    """
    try:
        from ctypes import windll
    except ImportError:
        return
    for call in (lambda: windll.shcore.SetProcessDpiAwareness(1),
                 lambda: windll.user32.SetProcessDPIAware()):
        try:
            call()
            return
        except Exception:
            continue


class CounterApp(object):
    """Окно: выбор папки, ввод выполненной программы, таблица готовности."""

    def __init__(self, master: tk.Misc, start_dir: Optional[str] = None) -> None:
        self.master = master
        self.summary: Optional[ShiftSummary] = None
        self.statuses: List[PartStatus] = []
        self.check = None
        self.directory: Optional[str] = None

        self.var_dir = tk.StringVar(value='папка не выбрана')
        self.var_done = tk.StringVar()
        self.var_search = tk.StringVar()
        self.var_only = tk.StringVar(value=presentation.ONLY_ALL)
        self.var_counters = tk.StringVar(value='Папка со сменным заданием не выбрана')
        self.var_check = tk.StringVar(value='')

        self._build()
        # trace_add, а не устаревший trace: последний удалён в Python 3.13,
        # а исходник собирают не только под целевой 3.8.
        self.var_search.trace_add('write', lambda *_: self._refresh_table())
        self.var_only.trace_add('write', lambda *_: self._refresh_table())

        if start_dir:
            self._load(start_dir)

    # --- построение окна ---

    def _build(self):
        self.master.title(TITLE)
        self.master.minsize(760, 480)
        root = ttk.Frame(self.master, padding=10)
        root.pack(fill='both', expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        root.grid_rowconfigure(2, weight=1)
        self._build_source(root)
        self._build_controls(root)
        self._build_table(root)
        self._build_footer(root)

    def _build_source(self, parent):
        box = ttk.LabelFrame(parent, text=' Сменное задание ', padding=8)
        box.grid(row=0, column=0, sticky='ew')
        box.columnconfigure(1, weight=1)

        ttk.Button(box, text='Выбрать папку с программами…',
                   command=self._choose_dir).grid(row=0, column=0, sticky='w')
        ttk.Label(box, textvariable=self.var_dir, font=FONT,
                  foreground=COLOR_MUTED).grid(row=0, column=1, sticky='w', padx=(10, 0))
        self.btn_reload = ttk.Button(box, text='Перечитать',
                                     command=self._reload, state='disabled')
        self.btn_reload.grid(row=0, column=2, sticky='e', padx=(10, 0))

    def _build_controls(self, parent):
        box = ttk.Frame(parent, padding=(0, 10, 0, 6))
        box.grid(row=1, column=0, sticky='ew')
        box.columnconfigure(6, weight=1)

        ttk.Label(box, text='Выполнено программ по №:',
                  font=FONT_BOLD).grid(row=0, column=0, sticky='w')
        entry = ttk.Entry(box, textvariable=self.var_done, width=7,
                          font=FONT_BIG, justify='center')
        entry.grid(row=0, column=1, sticky='w', padx=(8, 8))
        entry.bind('<Return>', lambda _: self._recalculate())
        self.entry_done = entry

        ttk.Button(box, text='Рассчитать',
                   command=self._recalculate).grid(row=0, column=2, sticky='w')

        ttk.Separator(box, orient='vertical').grid(row=0, column=3, sticky='ns', padx=14)

        ttk.Label(box, text='Показывать:', font=FONT).grid(row=0, column=4, sticky='w')
        choices = ttk.Frame(box)
        choices.grid(row=0, column=5, sticky='w', padx=(8, 0))
        for index, (value, label) in enumerate((
                (presentation.ONLY_ALL, 'все'),
                (presentation.ONLY_DONE, 'готовые'),
                (presentation.ONLY_WORK, 'в работе'))):
            ttk.Radiobutton(choices, text=label, value=value,
                            variable=self.var_only).grid(row=0, column=index, padx=(0, 10))

        search_box = ttk.Frame(box)
        search_box.grid(row=0, column=6, sticky='e')
        ttk.Label(search_box, text='Поиск позиции:', font=FONT).grid(row=0, column=0)
        ttk.Entry(search_box, textvariable=self.var_search, width=18,
                  font=FONT).grid(row=0, column=1, padx=(8, 0))

    def _build_table(self, parent):
        box = ttk.Frame(parent)
        box.grid(row=2, column=0, sticky='nsew')
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(box, columns=presentation.COLUMNS,
                                 show='headings', selectmode='browse')
        for index, name in enumerate(presentation.COLUMNS):
            self.tree.heading(name, text=name)
            self.tree.column(name, width=COLUMN_WIDTHS[index],
                             anchor=COLUMN_ANCHORS[index],
                             stretch=(index == 0))
        self.tree.tag_configure('done', background=COLOR_DONE_BG,
                                foreground=COLOR_DONE_FG)
        self.tree.grid(row=0, column=0, sticky='nsew')

        bar = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        bar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=bar.set)

    def _build_footer(self, parent):
        box = ttk.Frame(parent, padding=(0, 8, 0, 0))
        box.grid(row=3, column=0, sticky='ew')
        box.columnconfigure(0, weight=1)

        ttk.Label(box, textvariable=self.var_counters,
                  font=FONT_BOLD).grid(row=0, column=0, sticky='w')

        self.lbl_check = ttk.Label(box, textvariable=self.var_check, font=FONT)
        self.lbl_check.grid(row=1, column=0, sticky='w', pady=(2, 0))

        buttons = ttk.Frame(box)
        buttons.grid(row=0, column=1, rowspan=2, sticky='e')
        self.btn_warnings = ttk.Button(buttons, text='Замечания',
                                       command=self._show_warnings, state='disabled')
        self.btn_warnings.grid(row=0, column=0, padx=(0, 8))
        self.btn_export = ttk.Button(buttons, text='Выгрузить в CSV…',
                                     command=self._export, state='disabled')
        self.btn_export.grid(row=0, column=1)

        ttk.Label(parent, font=FONT, foreground=COLOR_MUTED,
                  text='Режим «только чтение»: файлы программ не изменяются, '
                       'стойка станка не затрагивается.'
                  ).grid(row=4, column=0, sticky='w', pady=(8, 0))

    # --- действия ---

    def _choose_dir(self):
        chosen = filedialog.askdirectory(
            title='Папка с управляющими программами',
            initialdir=self.directory or os.path.expanduser('~'))
        if chosen:
            self._load(chosen)

    def _reload(self):
        if self.directory:
            self._load(self.directory)

    def _load(self, directory: str) -> None:
        try:
            summary = balance.load_shift(directory, DEFAULT_SYNTAX)
        except (NotADirectoryError, OSError) as exc:
            messagebox.showerror(TITLE, 'Не удалось прочитать папку.\n\n{}'.format(exc))
            return

        if not summary.parts:
            messagebox.showwarning(
                TITLE,
                'В папке нет пригодных программ.\n\n{}'.format(
                    '\n'.join(summary.warnings) or 'Файлы управляющих программ не найдены.'))
            return

        self.directory = directory
        self.summary = summary
        self.check = balance.cross_check(summary.programs, DEFAULT_SYNTAX)

        self.var_dir.set(directory)
        self.btn_reload.configure(state='normal')
        self.btn_export.configure(state='normal')
        self.btn_warnings.configure(
            state='normal' if summary.warnings else 'disabled',
            text='Замечания ({})'.format(len(summary.warnings)) if summary.warnings
            else 'Замечания')

        self._show_cross_check()
        self._recalculate()
        self.entry_done.focus_set()

    def _done_number(self) -> Optional[int]:
        text = self.var_done.get().strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            messagebox.showwarning(
                TITLE, 'Номер выполненной программы вводится числом.\n\n'
                       'Пустое поле — смена ещё не начата.')
            return None

    def _recalculate(self):
        if self.summary is None:
            return
        done = self._done_number()
        if done is not None and self.summary.program_numbers:
            last = max(self.summary.program_numbers)
            if done > last:
                messagebox.showinfo(
                    TITLE, 'В задании {} программ. Показано как полностью '
                           'отработанная смена.'.format(last))
        self.statuses = balance.status_at(self.summary, done)
        self._refresh_table()

    def _refresh_table(self):
        if self.summary is None:
            return
        shown = presentation.filter_statuses(
            self.statuses, self.var_only.get(), self.var_search.get())

        self.tree.delete(*self.tree.get_children())
        for status in shown:
            self.tree.insert('', 'end',
                             values=presentation.row(status),
                             tags=('done',) if status.is_complete else ())

        self.var_counters.set(presentation.counters(self.summary, self.statuses))

    def _show_cross_check(self):
        text = presentation.cross_check_line(self.check)
        self.var_check.set(text)
        if self.check is not None and self.check.mismatches:
            colour = COLOR_ERROR
        elif self.check is not None and self.check.checked:
            colour = COLOR_OK
        else:
            colour = COLOR_WARN
        self.lbl_check.configure(foreground=colour)

    def _show_warnings(self):
        if not self.summary or not self.summary.warnings:
            return
        messagebox.showwarning(
            TITLE, 'Замечания при разборе файлов:\n\n{}'.format(
                '\n'.join('• ' + w for w in self.summary.warnings)))

    def _export(self):
        if self.summary is None:
            return
        shown = presentation.filter_statuses(
            self.statuses, self.var_only.get(), self.var_search.get())
        if not shown:
            messagebox.showinfo(TITLE, 'Выгружать нечего: список пуст.')
            return
        path = filedialog.asksaveasfilename(
            title='Сохранить выгрузку',
            defaultextension='.csv',
            initialfile='готовность.csv',
            filetypes=[('Таблица CSV', '*.csv'), ('Все файлы', '*.*')])
        if not path:
            return
        try:
            presentation.write_csv(path, shown, self._done_number())
        except OSError as exc:
            messagebox.showerror(TITLE, 'Не удалось сохранить файл.\n\n{}'.format(exc))
            return
        messagebox.showinfo(TITLE, 'Сохранено:\n{}'.format(path))


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    start_dir = argv[0] if argv and os.path.isdir(argv[0]) else None

    _enable_dpi_awareness()
    root = tk.Tk()
    try:
        ttk.Style().theme_use('vista')
    except tk.TclError:
        pass
    CounterApp(root, start_dir=start_dir)
    root.mainloop()
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
