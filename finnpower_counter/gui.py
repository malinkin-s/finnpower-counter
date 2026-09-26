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

from . import i18n, presentation
from .core import balance
from .core.model import PartStatus, ShiftSummary
from .core.syntax import DEFAULT_SYNTAX

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

        self.var_dir = tk.StringVar(value=i18n.t('ui.no_dir'))
        self.var_done = tk.StringVar()
        self.var_search = tk.StringVar()
        self.var_only = tk.StringVar(value=presentation.ONLY_ALL)
        self.var_counters = tk.StringVar(value=i18n.t('counters.empty'))
        self.var_lang = tk.StringVar(value=i18n.current())
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
        self.master.title(i18n.t('app.title'))
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
        box = ttk.LabelFrame(parent, text=i18n.t('ui.shift'), padding=8)
        self.box_shift = box
        box.grid(row=0, column=0, sticky='ew')
        box.columnconfigure(1, weight=1)

        self.btn_choose = ttk.Button(box, text=i18n.t('ui.choose_dir'),
                                     command=self._choose_dir)
        self.btn_choose.grid(row=0, column=0, sticky='w')
        ttk.Label(box, textvariable=self.var_dir, font=FONT,
                  foreground=COLOR_MUTED).grid(row=0, column=1, sticky='w', padx=(10, 0))
        self.btn_reload = ttk.Button(box, text=i18n.t('ui.reload'),
                                     command=self._reload, state='disabled')
        self.btn_reload.grid(row=0, column=2, sticky='e', padx=(10, 0))

        self.lbl_lang = ttk.Label(box, text=i18n.t('ui.language'), font=FONT)
        self.lbl_lang.grid(row=0, column=3, sticky='e', padx=(16, 4))
        self.cmb_lang = ttk.Combobox(
            box, state='readonly', width=10, font=FONT,
            values=[i18n.language_name(code) for code in i18n.available()])
        self.cmb_lang.current(i18n.available().index(i18n.current()))
        self.cmb_lang.grid(row=0, column=4, sticky='e')
        self.cmb_lang.bind('<<ComboboxSelected>>', self._change_language)

    def _build_controls(self, parent):
        box = ttk.Frame(parent, padding=(0, 10, 0, 6))
        box.grid(row=1, column=0, sticky='ew')
        box.columnconfigure(6, weight=1)

        self.lbl_done = ttk.Label(box, text=i18n.t('ui.done_label'), font=FONT_BOLD)
        self.lbl_done.grid(row=0, column=0, sticky='w')
        entry = ttk.Entry(box, textvariable=self.var_done, width=7,
                          font=FONT_BIG, justify='center')
        entry.grid(row=0, column=1, sticky='w', padx=(8, 8))
        entry.bind('<Return>', lambda _: self._recalculate())
        self.entry_done = entry

        self.btn_calc = ttk.Button(box, text=i18n.t('ui.calculate'),
                                   command=self._recalculate)
        self.btn_calc.grid(row=0, column=2, sticky='w')

        ttk.Separator(box, orient='vertical').grid(row=0, column=3, sticky='ns', padx=14)

        self.lbl_show = ttk.Label(box, text=i18n.t('ui.show'), font=FONT)
        self.lbl_show.grid(row=0, column=4, sticky='w')
        choices = ttk.Frame(box)
        choices.grid(row=0, column=5, sticky='w', padx=(8, 0))
        self.radios = {}
        for index, (value, key) in enumerate((
                (presentation.ONLY_ALL, 'ui.only_all'),
                (presentation.ONLY_DONE, 'ui.only_done'),
                (presentation.ONLY_WORK, 'ui.only_work'))):
            button = ttk.Radiobutton(choices, text=i18n.t(key), value=value,
                                     variable=self.var_only)
            button.grid(row=0, column=index, padx=(0, 10))
            self.radios[key] = button

        search_box = ttk.Frame(box)
        search_box.grid(row=0, column=6, sticky='e')
        self.lbl_search = ttk.Label(search_box, text=i18n.t('ui.search'), font=FONT)
        self.lbl_search.grid(row=0, column=0)
        ttk.Entry(search_box, textvariable=self.var_search, width=18,
                  font=FONT).grid(row=0, column=1, padx=(8, 0))

    def _build_table(self, parent):
        box = ttk.Frame(parent)
        box.grid(row=2, column=0, sticky='nsew')
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(box, columns=presentation.COLUMN_KEYS,
                                 show='headings', selectmode='browse')
        for index, key in enumerate(presentation.COLUMN_KEYS):
            self.tree.column(key, width=COLUMN_WIDTHS[index],
                             anchor=COLUMN_ANCHORS[index],
                             stretch=(index == 0))
        self._apply_headings()
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
        self.btn_warnings = ttk.Button(buttons, text=i18n.t('ui.warnings'),
                                       command=self._show_warnings, state='disabled')
        self.btn_warnings.grid(row=0, column=0, padx=(0, 8))
        self.btn_export = ttk.Button(buttons, text=i18n.t('ui.export'),
                                     command=self._export, state='disabled')
        self.btn_export.grid(row=0, column=1)

        self.lbl_readonly = ttk.Label(parent, font=FONT, foreground=COLOR_MUTED,
                                      text=i18n.t('app.readonly'), wraplength=700)
        self.lbl_readonly.grid(row=4, column=0, sticky='w', pady=(8, 0))

    # --- язык ---

    def _apply_headings(self) -> None:
        for key, title in zip(presentation.COLUMN_KEYS, presentation.columns()):
            self.tree.heading(key, text=title)

    def _change_language(self, _event=None) -> None:
        code = i18n.available()[self.cmb_lang.current()]
        if code == i18n.current():
            return
        i18n.set_language(code)
        self._retranslate()

    def _retranslate(self) -> None:
        """Переписать все подписи на текущем языке.

        Замечания и расхождения хранятся ключами, а не готовыми строками,
        поэтому перечитывать файлы не нужно — достаточно перерисовать.
        """
        self.master.title(i18n.t('app.title'))
        self.box_shift.configure(text=i18n.t('ui.shift'))
        self.btn_choose.configure(text=i18n.t('ui.choose_dir'))
        self.btn_reload.configure(text=i18n.t('ui.reload'))
        self.lbl_lang.configure(text=i18n.t('ui.language'))
        self.lbl_done.configure(text=i18n.t('ui.done_label'))
        self.btn_calc.configure(text=i18n.t('ui.calculate'))
        self.lbl_show.configure(text=i18n.t('ui.show'))
        for key, button in self.radios.items():
            button.configure(text=i18n.t(key))
        self.lbl_search.configure(text=i18n.t('ui.search'))
        self.btn_export.configure(text=i18n.t('ui.export'))
        self.lbl_readonly.configure(text=i18n.t('app.readonly'))
        self.cmb_lang.configure(
            values=[i18n.language_name(code) for code in i18n.available()])
        self.cmb_lang.current(i18n.available().index(i18n.current()))

        self._apply_headings()

        if self.summary is None:
            self.var_dir.set(i18n.t('ui.no_dir'))
            self.var_counters.set(i18n.t('counters.empty'))
            self.btn_warnings.configure(text=i18n.t('ui.warnings'))
            return

        self.btn_warnings.configure(
            text=i18n.t('ui.warnings_n', count=len(self.summary.warnings))
            if self.summary.warnings else i18n.t('ui.warnings'))
        self._show_cross_check()
        self._refresh_table()

    # --- действия ---

    def _choose_dir(self):
        chosen = filedialog.askdirectory(
            title=i18n.t('dlg.choose_dir'),
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
            messagebox.showerror(i18n.t('app.title'),
                                 i18n.t('dlg.read_failed', error=exc))
            return

        if not summary.parts:
            messagebox.showwarning(
                i18n.t('app.title'),
                i18n.t('dlg.no_programs',
                       details='\n'.join(str(w) for w in summary.warnings)
                       or i18n.t('dlg.no_programs_plain')))
            return

        self.directory = directory
        self.summary = summary
        self.check = balance.cross_check(summary.programs, DEFAULT_SYNTAX)

        self.var_dir.set(directory)
        self.btn_reload.configure(state='normal')
        self.btn_export.configure(state='normal')
        self.btn_warnings.configure(
            state='normal' if summary.warnings else 'disabled',
            text=i18n.t('ui.warnings_n', count=len(summary.warnings))
            if summary.warnings else i18n.t('ui.warnings'))

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
            messagebox.showwarning(i18n.t('app.title'), i18n.t('dlg.not_a_number'))
            return None

    def _recalculate(self):
        if self.summary is None:
            return
        done = self._done_number()
        if done is not None and self.summary.program_numbers:
            last = max(self.summary.program_numbers)
            if done > last:
                messagebox.showinfo(i18n.t('app.title'),
                                    i18n.t('dlg.beyond_shift', last=last))
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
        if not shown:
            self.tree.insert('', 'end',
                             values=(i18n.t('table.empty'), '', '', '', ''))

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
            i18n.t('app.title'),
            i18n.t('dlg.warnings',
                   items='\n'.join('• ' + str(w) for w in self.summary.warnings)))

    def _export(self):
        if self.summary is None:
            return
        shown = presentation.filter_statuses(
            self.statuses, self.var_only.get(), self.var_search.get())
        if not shown:
            messagebox.showinfo(i18n.t('app.title'), i18n.t('dlg.nothing_to_export'))
            return
        path = filedialog.asksaveasfilename(
            title=i18n.t('dlg.save_as'),
            defaultextension='.csv',
            initialfile=i18n.t('dlg.default_name'),
            filetypes=[(i18n.t('dlg.csv_files'), '*.csv'),
                       (i18n.t('dlg.all_files'), '*.*')])
        if not path:
            return
        try:
            presentation.write_csv(path, shown, self._done_number())
        except OSError as exc:
            messagebox.showerror(i18n.t('app.title'),
                                 i18n.t('dlg.save_failed', error=exc))
            return
        messagebox.showinfo(i18n.t('app.title'), i18n.t('dlg.saved', path=path))


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    language = None
    for item in list(argv):
        if item.startswith('--lang='):
            language = item.split('=', 1)[1]
            argv.remove(item)
    i18n.set_language(language or i18n.detect())

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
