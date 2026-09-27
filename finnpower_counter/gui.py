# -*- coding: utf-8 -*-
"""Окно оператора.

Рабочая версия для цеха. Только чтение: утилита разбирает копии текстовых
файлов и ничего не пишет ни в программы, ни в стойку станка. Единственное
действие наружу — открыть карту наладки той программой, которая назначена
в системе.

Модуль намеренно тонкий. Отбор, состав колонок, выравнивание и выгрузка живут
в presentation, расчёт — в core, поэтому проверяются тестами без поднятия
окна. Здесь остаются размещение элементов и реакция на действия оператора.

Цель сборки — Windows 7 32-bit, Python 3.8.10: tkinter из стандартной
библиотеки, никаких внешних зависимостей.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set

from . import i18n, presentation, system
from .core import balance, fms_parser
from .core.model import PartStatus, PartTotal, ShiftSummary
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

# Ширины колонок по режимам, в пикселях при 96 DPI.
COLUMN_WIDTHS = {
    presentation.MODE_PARTS: (180, 130, 120, 120, 110),
    presentation.MODE_PROGRAMS: (36, 130, 120, 70, 80, 80, 120),
}
DETAIL_WIDTHS = (120, 80, 90, 100, 110)

ANCHORS = {'l': 'w', 'r': 'e', 'c': 'center'}

# Обозначения строк таблицы. По ним двойной щелчок понимает, на что нажали.
ROW_PART = 'part:'
ROW_PROGRAM = 'prog:'
ROW_EMPTY = 'empty'


def _enable_dpi_awareness() -> None:
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


def _configure_tree(tree: ttk.Treeview, keys, titles, widths, align,
                    on_heading=None) -> None:
    """Переназначить колонки таблицы. Нужно при смене режима и языка."""
    tree.configure(columns=list(keys))
    for index, key in enumerate(keys):
        if on_heading is None:
            tree.heading(key, text=titles[index])
        else:
            tree.heading(key, text=titles[index],
                         command=lambda k=key: on_heading(k))
        tree.column(key,
                    width=widths[index],
                    anchor=ANCHORS.get(align[index], 'w'),
                    stretch=(index == 1 if len(keys) > 5 else index == 0))


class PartWindow(object):
    """Отдельное окно одной позиции: в каких программах и по сколько.

    Немодальное: оператор держит его открытым, пока работает с таблицей,
    и может открыть сразу несколько.
    """

    def __init__(self, master: tk.Misc, part: PartTotal,
                 summary: ShiftSummary, on_close) -> None:
        self.part = part
        self.summary = summary
        self._on_close = on_close

        self.top = tk.Toplevel(master)
        self.top.minsize(560, 260)
        self.top.protocol('WM_DELETE_WINDOW', self.close)

        frame = ttk.Frame(self.top, padding=10)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self.lbl_summary = ttk.Label(frame, font=FONT_BOLD)
        self.lbl_summary.grid(row=0, column=0, sticky='w', pady=(0, 8))

        table = ttk.Frame(frame)
        table.grid(row=1, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(table, show='headings', selectmode='browse',
                                 height=min(12, max(3, len(part.by_program))))
        self.tree.grid(row=0, column=0, sticky='nsew')
        bar = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        bar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=bar.set)

        self.btn_close = ttk.Button(frame, command=self.close)
        self.btn_close.grid(row=2, column=0, sticky='e', pady=(10, 0))

        self.retranslate()

    def retranslate(self) -> None:
        self.top.title(i18n.t('detail.title',
                              part=self.part.part,
                              total=self.part.total,
                              last=self.part.last_program))
        self.lbl_summary.configure(text=i18n.t(
            'detail.summary',
            total=self.part.total,
            count=len(self.part.by_program),
            last=self.part.last_program))
        self.btn_close.configure(text=i18n.t('detail.close'))
        _configure_tree(self.tree,
                        presentation.DETAIL_COLUMN_KEYS,
                        presentation.detail_columns(),
                        DETAIL_WIDTHS,
                        presentation.DETAIL_ALIGN)
        self.refresh()

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in presentation.part_detail_rows(self.part, self.summary.programs):
            self.tree.insert('', 'end', values=row)

    def focus(self) -> None:
        self.top.deiconify()
        self.top.lift()
        self.top.focus_force()

    def close(self) -> None:
        self._on_close(self.part.part)
        self.top.destroy()


class CounterApp(object):
    """Окно: выбор папки, ввод выполненной программы, таблица готовности."""

    def __init__(self, master: tk.Misc, start_dir: Optional[str] = None) -> None:
        self.master = master
        self.summary: Optional[ShiftSummary] = None
        self.statuses: List[PartStatus] = []
        self.check = None
        self.directory: Optional[str] = None
        self.detail_windows: Dict[str, PartWindow] = {}
        # Выполненные программы хранятся набором мест, а не одним числом:
        # программы не всегда идут подряд, и оператор снимает отметки вручную.
        self.done_positions: Set[int] = set()
        self.sort_column: Optional[str] = None
        self.sort_reverse = False

        self.var_dir = tk.StringVar(value=i18n.t('ui.no_dir'))
        self.var_done = tk.StringVar()
        self.var_search = tk.StringVar()
        self.var_only = tk.StringVar(value=presentation.ONLY_ALL)
        self.var_mode = tk.StringVar(value=presentation.MODE_PARTS)
        self.var_counters = tk.StringVar(value=i18n.t('counters.empty'))
        self.var_lang = tk.StringVar(value=i18n.current())
        self.var_check = tk.StringVar(value='')
        self.var_hint = tk.StringVar(value='')

        self._build()
        # trace_add, а не устаревший trace: последний удалён в Python 3.13,
        # а исходник собирают не только под целевой 3.8.
        self.var_search.trace_add('write', lambda *_: self._refresh_table())
        self.var_only.trace_add('write', lambda *_: self._refresh_table())
        self.var_mode.trace_add('write', lambda *_: self._change_mode())

        self._change_mode()
        if start_dir:
            self._load(start_dir)

    # --- построение окна ---

    def _build(self) -> None:
        self.master.title(i18n.t('app.title'))
        self.master.minsize(860, 520)
        root = ttk.Frame(self.master, padding=10)
        root.pack(fill='both', expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        self._build_source(root)
        self._build_controls(root)
        self._build_table(root)
        self._build_footer(root)

    def _build_source(self, parent: tk.Misc) -> None:
        box = ttk.LabelFrame(parent, text=i18n.t('ui.shift'), padding=8)
        box.grid(row=0, column=0, sticky='ew')
        box.columnconfigure(1, weight=1)
        self.box_shift = box

        self.btn_choose = ttk.Button(box, text=i18n.t('ui.choose_dir'),
                                     command=self._choose_dir)
        self.btn_choose.grid(row=0, column=0, sticky='w')
        ttk.Label(box, textvariable=self.var_dir, font=FONT,
                  foreground=COLOR_MUTED).grid(row=0, column=1, sticky='w',
                                               padx=(10, 0))
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

    def _build_controls(self, parent: tk.Misc) -> None:
        """Две строки, а не одна.

        В одну строку всё это требует около 1250 пикселей — при минимальной
        ширине окна элементы наезжали друг на друга. Левые блоки собраны
        в отдельные рамки и растут по содержимому, между ними и поиском
        стоит пустая колонка-распорка.
        """
        box = ttk.Frame(parent, padding=(0, 10, 0, 6))
        box.grid(row=1, column=0, sticky='ew')
        box.columnconfigure(1, weight=1)

        # --- верхняя строка: выполненная программа и поиск ---
        top = ttk.Frame(box)
        top.grid(row=0, column=0, sticky='w')

        self.lbl_done = ttk.Label(top, text=i18n.t('ui.done_label'), font=FONT_BOLD)
        self.lbl_done.grid(row=0, column=0, sticky='w')
        entry = ttk.Entry(top, textvariable=self.var_done, width=16,
                          font=FONT_BIG, justify='center')
        entry.grid(row=0, column=1, sticky='w', padx=(8, 8))
        entry.bind('<Return>', lambda _: self._recalculate())
        self.entry_done = entry
        self.btn_calc = ttk.Button(top, text=i18n.t('ui.calculate'),
                                   command=self._recalculate)
        self.btn_calc.grid(row=0, column=2, sticky='w')

        search_box = ttk.Frame(box)
        search_box.grid(row=0, column=2, sticky='e')
        self.lbl_search = ttk.Label(search_box, text=i18n.t('ui.search_parts'),
                                    font=FONT)
        self.lbl_search.grid(row=0, column=0)
        ttk.Entry(search_box, textvariable=self.var_search, width=20,
                  font=FONT).grid(row=0, column=1, padx=(8, 0))

        # --- нижняя строка: режим и отбор ---
        bottom = ttk.Frame(box)
        bottom.grid(row=1, column=0, columnspan=3, sticky='w', pady=(8, 0))

        self.lbl_mode = ttk.Label(bottom, text=i18n.t('ui.mode'), font=FONT)
        self.lbl_mode.grid(row=0, column=0, sticky='w')
        modes = ttk.Frame(bottom)
        modes.grid(row=0, column=1, sticky='w', padx=(8, 0))
        self.mode_buttons = {}
        for index, (value, key) in enumerate((
                (presentation.MODE_PARTS, 'ui.mode_parts'),
                (presentation.MODE_PROGRAMS, 'ui.mode_programs'))):
            button = ttk.Radiobutton(modes, text=i18n.t(key), value=value,
                                     variable=self.var_mode)
            button.grid(row=0, column=index, padx=(0, 10))
            self.mode_buttons[key] = button

        ttk.Separator(bottom, orient='vertical').grid(row=0, column=2,
                                                      sticky='ns', padx=14)

        self.lbl_show = ttk.Label(bottom, text=i18n.t('ui.show'), font=FONT)
        self.lbl_show.grid(row=0, column=3, sticky='w')
        choices = ttk.Frame(bottom)
        choices.grid(row=0, column=4, sticky='w', padx=(8, 0))
        self.radios = {}
        for index, (value, key) in enumerate((
                (presentation.ONLY_ALL, 'ui.only_all'),
                (presentation.ONLY_DONE, 'ui.only_done'),
                (presentation.ONLY_WORK, 'ui.only_work'))):
            button = ttk.Radiobutton(choices, text=i18n.t(key), value=value,
                                     variable=self.var_only)
            button.grid(row=0, column=index, padx=(0, 10))
            self.radios[key] = button

    def _build_table(self, parent: tk.Misc) -> None:
        box = ttk.Frame(parent)
        box.grid(row=2, column=0, sticky='nsew')
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(box, show='headings', selectmode='browse')
        self.tree.tag_configure('done', background=COLOR_DONE_BG,
                                foreground=COLOR_DONE_FG)
        self.tree.tag_configure('empty', foreground=COLOR_MUTED)
        self.tree.grid(row=0, column=0, sticky='nsew')
        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Button-1>', self._toggle_program)
        self.tree.bind('<Shift-Button-1>',
                       lambda e: self._toggle_program(e, upto=True))

        bar = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        bar.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=bar.set)

        self.lbl_hint = ttk.Label(parent, textvariable=self.var_hint,
                                  font=FONT, foreground=COLOR_MUTED)
        self.lbl_hint.grid(row=3, column=0, sticky='w', pady=(4, 0))

    def _build_footer(self, parent: tk.Misc) -> None:
        box = ttk.Frame(parent, padding=(0, 8, 0, 0))
        box.grid(row=4, column=0, sticky='ew')
        box.columnconfigure(0, weight=1)

        ttk.Label(box, textvariable=self.var_counters,
                  font=FONT_BOLD).grid(row=0, column=0, sticky='w')
        self.lbl_check = ttk.Label(box, textvariable=self.var_check, font=FONT)
        self.lbl_check.grid(row=1, column=0, sticky='w', pady=(2, 0))

        buttons = ttk.Frame(box)
        buttons.grid(row=0, column=1, rowspan=2, sticky='e')
        self.btn_warnings = ttk.Button(buttons, text=i18n.t('ui.warnings'),
                                       command=self._show_warnings,
                                       state='disabled')
        self.btn_warnings.grid(row=0, column=0, padx=(0, 8))
        self.btn_export = ttk.Button(buttons, text=i18n.t('ui.export'),
                                     command=self._export, state='disabled')
        self.btn_export.grid(row=0, column=1)

        self.lbl_readonly = ttk.Label(parent, font=FONT, foreground=COLOR_MUTED,
                                      text=i18n.t('app.readonly'), wraplength=800)
        self.lbl_readonly.grid(row=5, column=0, sticky='w', pady=(8, 0))

    # --- режим показа ---

    @property
    def mode(self) -> str:
        return self.var_mode.get()

    def _change_mode(self, *_args) -> None:
        """Переключить режим: другие колонки, другая подпись поиска.

        Строка поиска намеренно не очищается — если оператор ищет PRG_07,
        а потом переключается на детали, он сам решит, что делать с текстом.
        """
        mode = self.mode
        by_programs = mode == presentation.MODE_PROGRAMS
        self.lbl_search.configure(
            text=i18n.t('ui.search_programs' if by_programs else 'ui.search_parts'))
        self.var_hint.set(
            i18n.t('ui.hint_programs' if by_programs else 'ui.hint_parts'))
        self.sort_column = None
        self.sort_reverse = False
        _configure_tree(self.tree,
                        presentation.column_keys(mode),
                        presentation.columns(mode),
                        COLUMN_WIDTHS[mode],
                        presentation.align(mode),
                        on_heading=self._sort_by)
        self._refresh_table()

    def _sort_by(self, column: str) -> None:
        """Щелчок по заголовку: сортировать по колонке, повторный — обратно."""
        if not presentation.sortable(self.mode, column):
            return
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self._apply_headings()
        self._refresh_table()

    def _apply_headings(self) -> None:
        for key in presentation.column_keys(self.mode):
            self.tree.heading(key, text=presentation.heading(
                key, self.sort_column, self.sort_reverse))

    # --- язык ---

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
        self.lbl_mode.configure(text=i18n.t('ui.mode'))
        for key, button in self.mode_buttons.items():
            button.configure(text=i18n.t(key))
        self.lbl_show.configure(text=i18n.t('ui.show'))
        for key, button in self.radios.items():
            button.configure(text=i18n.t(key))
        self.btn_export.configure(text=i18n.t('ui.export'))
        self.lbl_readonly.configure(text=i18n.t('app.readonly'))
        self.cmb_lang.configure(
            values=[i18n.language_name(code) for code in i18n.available()])
        self.cmb_lang.current(i18n.available().index(i18n.current()))

        for window in list(self.detail_windows.values()):
            window.retranslate()
        self._apply_headings()

        if self.summary is None:
            self.var_dir.set(i18n.t('ui.no_dir'))
            self.var_counters.set(i18n.t('counters.empty'))
            self.btn_warnings.configure(text=i18n.t('ui.warnings'))
            self._change_mode()
            return

        self.btn_warnings.configure(
            text=i18n.t('ui.warnings_n', count=len(self.summary.warnings))
            if self.summary.warnings else i18n.t('ui.warnings'))
        self._show_cross_check()
        self._change_mode()

    # --- действия ---

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title=i18n.t('dlg.choose_dir'),
            initialdir=self.directory or os.path.expanduser('~'))
        if chosen:
            self._load(chosen)

    def _reload(self) -> None:
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

        # Открытые окна позиций относятся к прежнему заданию.
        self._close_detail_windows()

        self.directory = directory
        self.summary = summary
        self.check = balance.cross_check(summary.programs, DEFAULT_SYNTAX)
        self.done_positions = set()
        self.sort_column = None
        self.sort_reverse = False
        self.var_done.set('')

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

    def _recalculate(self) -> None:
        """Ввод номера — быстрый способ отметить всё подряд до указанной УП.

        Дальше отметки правятся галочками: программы не всегда идут по порядку.
        """
        if self.summary is None:
            return
        try:
            done = balance.resolve_position(self.summary, self.var_done.get())
        except ValueError as exc:
            messagebox.showwarning(i18n.t('app.title'), str(exc.args[0]))
            return
        self.done_positions = balance.positions_upto(self.summary, done)
        self._restate()

    def _restate(self) -> None:
        """Пересчитать готовность по текущему набору отметок."""
        if self.summary is None:
            return
        self.statuses = balance.status_for(self.summary, self.done_positions)
        self._refresh_table()
        for window in self.detail_windows.values():
            window.refresh()

    def _refresh_table(self) -> None:
        if self.summary is None:
            return
        self.tree.delete(*self.tree.get_children())

        done = self.done_positions
        if self.mode == presentation.MODE_PROGRAMS:
            shown = presentation.sort_programs(
                presentation.filter_programs(
                    self.summary.usable_programs, self.var_only.get(),
                    self.var_search.get(), done),
                self.sort_column, self.sort_reverse, done)
            for nest in shown:
                executed = nest.position in done
                self.tree.insert('', 'end', iid=ROW_PROGRAM + nest.name,
                                 values=presentation.program_row(nest, done),
                                 tags=('done',) if executed else ())
            empty = not shown
        else:
            shown = presentation.sort_statuses(
                presentation.filter_statuses(
                    self.statuses, self.var_only.get(), self.var_search.get()),
                self.sort_column, self.sort_reverse)
            for status in shown:
                self.tree.insert('', 'end', iid=ROW_PART + status.part,
                                 values=presentation.row(status),
                                 tags=('done',) if status.is_complete else ())
            empty = not shown

        if empty:
            columns = len(presentation.column_keys(self.mode))
            self.tree.insert('', 'end', iid=ROW_EMPTY, tags=('empty',),
                             values=[i18n.t('table.empty')] + [''] * (columns - 1))

        self.var_counters.set(presentation.counters(self.summary, self.statuses))

    # --- отметки выполнения ---

    def _toggle_program(self, event, upto: bool = False) -> Optional[str]:
        """Щелчок по колонке отметки. С Shift — отметить всё до этой программы.

        Вернуть 'break' нужно, чтобы щелчок не уходил дальше и не открывал
        карту наладки: по этой же таблице работает двойной щелчок.
        """
        if self.summary is None or self.mode != presentation.MODE_PROGRAMS:
            return None
        if self.tree.identify_region(event.x, event.y) != 'cell':
            return None
        if self.tree.identify_column(event.x) != '#1':
            return None
        item = self.tree.identify_row(event.y)
        if not item or not item.startswith(ROW_PROGRAM):
            return None

        name = item[len(ROW_PROGRAM):]
        nest = next((n for n in self.summary.usable_programs if n.name == name), None)
        if nest is None:
            return 'break'

        if upto:
            self.done_positions = {p for p in self.summary.positions
                                   if p <= nest.position}
        elif nest.position in self.done_positions:
            self.done_positions.discard(nest.position)
        else:
            self.done_positions.add(nest.position)

        self._restate()
        return 'break'

    # --- двойной щелчок ---

    def _on_double_click(self, _event=None) -> None:
        item = self.tree.focus()
        if not item or item == ROW_EMPTY:
            return
        if item.startswith(ROW_PROGRAM):
            self._open_document(item[len(ROW_PROGRAM):])
        elif item.startswith(ROW_PART):
            self._open_part(item[len(ROW_PART):])

    def _open_document(self, program_name: str) -> None:
        """Открыть карту наладки программы системным приложением."""
        if self.summary is None:
            return
        nest = next((n for n in self.summary.programs if n.name == program_name), None)
        if nest is None or not nest.path:
            return
        document = fms_parser.find_document(nest.path, DEFAULT_SYNTAX)
        if document is None:
            messagebox.showinfo(i18n.t('app.title'),
                                i18n.t('doc.missing', program=program_name))
            return
        error = system.open_document(document)
        if error:
            messagebox.showerror(i18n.t('app.title'),
                                 i18n.t('doc.failed', error=error))

    def _open_part(self, part_name: str) -> None:
        """Открыть немодальное окно позиции. Повторный щелчок поднимает его."""
        if self.summary is None:
            return
        existing = self.detail_windows.get(part_name)
        if existing is not None:
            existing.focus()
            return
        part = next((p for p in self.summary.parts if p.part == part_name), None)
        if part is None:
            return
        self.detail_windows[part_name] = PartWindow(
            self.master, part, self.summary, self._forget_detail_window)

    def _forget_detail_window(self, part_name: str) -> None:
        self.detail_windows.pop(part_name, None)

    def _close_detail_windows(self) -> None:
        for window in list(self.detail_windows.values()):
            window.top.destroy()
        self.detail_windows.clear()

    # --- подвал ---

    def _show_cross_check(self) -> None:
        self.var_check.set(presentation.cross_check_line(self.check))
        if self.check is not None and self.check.mismatches:
            colour = COLOR_ERROR
        elif self.check is not None and self.check.checked:
            colour = COLOR_OK
        else:
            colour = COLOR_WARN
        self.lbl_check.configure(foreground=colour)

    def _show_warnings(self) -> None:
        if not self.summary or not self.summary.warnings:
            return
        messagebox.showwarning(
            i18n.t('app.title'),
            i18n.t('dlg.warnings',
                   items='\n'.join('• ' + str(w) for w in self.summary.warnings)))

    def _export(self) -> None:
        if self.summary is None:
            return
        shown = presentation.filter_statuses(
            self.statuses, self.var_only.get(),
            self.var_search.get() if self.mode == presentation.MODE_PARTS else None)
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
            presentation.write_csv(path, shown, len(self.done_positions))
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
