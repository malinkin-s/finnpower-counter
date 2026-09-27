# -*- coding: utf-8 -*-
"""Переводы интерфейса.

Словари прямо в коде, без gettext и внешних файлов. Причина простая: сборка
идёт в один файл через PyInstaller, и всё, что лежит отдельными .mo, нужно
отдельно класть в сборку и искать в рантайме. Словарь такой возни не требует
и не может потеряться при копировании .exe на другой компьютер.

Чтобы добавить язык, допишите в CATALOGS ещё один словарь с теми же ключами.
Недостающие ключи берутся из английского, так что перевод можно вести
частями — интерфейс останется рабочим.
"""

import os
from typing import Dict, List, Optional

FALLBACK = 'en'

LANGUAGE_NAMES = {
    'en': 'English',
    'ru': 'Русский',
}

CATALOGS: Dict[str, Dict[str, str]] = {

    'en': {
        # --- общее ---
        'app.title': 'Part completion tracker',
        'app.readonly': ('Read-only mode: program files are not modified, '
                         'the machine control is not touched.'),

        # --- колонки таблицы ---
        'col.part': 'Part',
        'col.total': 'Total in order',
        'col.last_program': 'Last program',
        'col.produced': 'Made so far',
        'col.status': 'Status',
        'col.mark': '\u2713',
        'col.program': 'Program',
        'col.sheet_size': 'Sheet size',
        'col.sheets': 'Sheets',
        'col.positions': 'Positions',
        'col.pieces': 'Pieces',
        'col.per_sheet': 'Per sheet',
        'col.in_program': 'In this program',
        'col.cumulative': 'Cumulative',

        # --- статусы ---
        'status.done': 'Done',
        'status.in_work': 'In progress',
        'status.executed': 'Executed',
        'status.pending': 'Pending',

        # --- итоги ---
        'counters': ('Programs: {programs}    Parts: {parts}    Pieces: {pieces}    '
                     'Fully done: {done} of {total}'),
        'counters.empty': 'No shift folder selected',
        'programs.done': 'Programs completed: {value}',
        'programs.not_started': 'shift not started',

        # --- сверка ---
        'check.none': 'Cross-check not performed',
        'check.not_found': 'Cross-check: no setup reports found',
        'check.mismatches': 'Cross-check: {count} mismatches in {checked} reports',
        'check.clean': 'Cross-checked against {checked} setup reports, no mismatches',
        'check.skipped': ' (without report: {count})',
        'check.skipped_line': 'Without setup report: {count} programs.',

        # --- расхождения ---
        'mismatch.sheets': '{program}: {mine} sheets in program, {theirs} in report',
        'mismatch.part': '{program}: {part} — {mine} in program, {theirs} in {section}',
        'mismatch.sheet_size': '{program}: sheet {mine} in program, {theirs} in report',

        # --- замечания при разборе ---
        'warn.no_sheet_count': 'no SHEET_COUNT declaration — quantity unknown',
        'warn.zero_sheets': 'SHEET_COUNT=0 — program yields no parts',
        'warn.block_skipped': 'PART_DATA block #{index} skipped: no {field}',
        'warn.only_scrap': 'only scrap contours in this program, no parts',
        'warn.encoding': 'file was read as {encoding}',
        'warn.no_programs': 'no program files in folder ({suffixes})',
        'warn.fms_no_sheets': 'report has no NUMBER OF SHEETS',
        'warn.fms_no_section': 'report has no {section} section',

        # --- окно ---
        'ui.shift': ' Shift task ',
        'ui.choose_dir': 'Choose program folder…',
        'ui.no_dir': 'no folder selected',
        'ui.reload': 'Reload',
        'ui.show': 'Show:',
        'ui.only_all': 'all',
        'ui.only_done': 'done',
        'ui.only_work': 'in progress',
        'ui.search': 'Find part:',
        'ui.warnings': 'Notes',
        'ui.warnings_n': 'Notes ({count})',
        'ui.export': 'Export to CSV…',
        'ui.language': 'Language:',
        'ui.mode': 'View:',
        'ui.mode_parts': 'by part',
        'ui.mode_programs': 'by program',
        'ui.search_parts': 'Part:',
        'ui.search_programs': 'Program:',
        'ui.hint_parts': ('Double-click a part to see its programs. '
                          'Mark completed programs in the "by program" view.'),
        'ui.hint_programs': ('Click the check column to mark a program done, '
                             'Shift+click to mark everything up to it. '
                             'Double-click a row to open its setup report.'),

        # --- окно позиции ---
        'detail.title': '{part} — {total} pcs, last program {last}',
        'detail.summary': 'Total {total} pcs in {count} programs, closes at {last}',
        'detail.close': 'Close',

        # --- карта наладки ---
        'done.ambiguous': ('"{text}" matches several programs: {names}.\n\n'
                           'Type the place in the shift or a longer part of the name.'),
        'done.unknown': ('No program matches "{text}".\n\n'
                         'Type its place in the shift or its name.'),

        'doc.missing': 'No setup report found next to program {program}.',
        'doc.failed': 'Could not open the setup report.\n\n{error}',

        # --- диалоги ---
        'dlg.choose_dir': 'Folder with NC programs',
        'dlg.read_failed': 'Could not read the folder.\n\n{error}',
        'dlg.no_programs': 'No usable programs in this folder.\n\n{details}',
        'dlg.no_programs_plain': 'No NC program files found.',
        'dlg.warnings': 'Notes from parsing:\n\n{items}',
        'dlg.nothing_to_export': 'Nothing to export: the list is empty.',
        'dlg.save_as': 'Save export',
        'dlg.default_name': 'completion.csv',
        'dlg.csv_files': 'CSV table',
        'dlg.all_files': 'All files',
        'dlg.save_failed': 'Could not save the file.\n\n{error}',
        'dlg.saved': 'Saved:\n{path}',

        # --- таблица / пусто ---
        'table.empty': 'Nothing matches the current filter.',
        'csv.done_programs': 'Programs completed:',

        # --- консоль ---
        'cli.description': 'Part completion tracking for a CNC shift task.',
        'cli.help.dir': 'folder with NC program files',
        'cli.help.done': ('number of the last completed program; '
                          'without it the shift counts as not started'),
        'cli.help.search': 'show only parts containing this text',
        'cli.help.only': 'which rows to show (default: all)',
        'cli.help.mode': 'list parts or programs (default: parts)',
        'cli.help.sort': 'sort by column ({choices})',
        'cli.help.desc': 'sort in descending order',
        'cli.error.sort': ('Error: cannot sort by "{value}" in this view.\n'
                           'Available: {choices}'),
        'cli.help.validate': 'cross-check parsing against .fms setup reports',
        'cli.help.json': 'output JSON instead of a table',
        'cli.help.lang': 'interface language ({choices})',
        'cli.error': 'Error: {message}',
        'cli.error.no_programs': 'Error: no usable programs in the folder.',
        'cli.check.clean': 'Cross-check against setup reports: {checked} programs, no mismatches.',
        'cli.check.mismatches': 'Cross-check against setup reports: {count} mismatches.',
        'cli.notes': 'Notes from parsing:',

        # --- ошибки ---
        'error.not_a_directory': 'no such folder: {path}',
        'error.unreadable': 'could not read the file: {details}',
    },

    'ru': {
        'app.title': 'Учёт готовности деталей',
        'app.readonly': ('Режим «только чтение»: файлы программ не изменяются, '
                         'стойка станка не затрагивается.'),

        'col.part': 'Артикул',
        'col.total': 'Всего в заказе',
        'col.last_program': 'Крайняя УП',
        'col.produced': 'Готово сейчас',
        'col.status': 'Статус',
        'col.mark': '\u2713',
        'col.program': 'Программа',
        'col.sheet_size': 'Размер листа',
        'col.sheets': 'Листов',
        'col.positions': 'Позиций',
        'col.pieces': 'Деталей',
        'col.per_sheet': 'На листе',
        'col.in_program': 'В этой УП',
        'col.cumulative': 'Накоплено',

        'status.done': 'Готово',
        'status.in_work': 'В работе',
        'status.executed': 'Выполнена',
        'status.pending': 'Не выполнена',

        'counters': ('Программ: {programs}    Позиций: {parts}    Деталей: {pieces}    '
                     'Готово полностью: {done} из {total}'),
        'counters.empty': 'Папка со сменным заданием не выбрана',
        'programs.done': 'Выполнено программ: {value}',
        'programs.not_started': 'смена не начата',

        'check.none': 'Сверка не выполнялась',
        'check.not_found': 'Сверка: отчёты наладки не найдены',
        'check.mismatches': 'Сверка: расхождений {count} в {checked} отчётах',
        'check.clean': 'Сверено с {checked} отчётами наладки, расхождений нет',
        'check.skipped': ' (без отчёта: {count})',
        'check.skipped_line': 'Без отчёта наладки: {count} программ.',

        'mismatch.sheets': '{program}: листов в программе {mine}, в отчёте {theirs}',
        'mismatch.part': '{program}: {part} — в программе {mine}, в {section} {theirs}',
        'mismatch.sheet_size': '{program}: лист {mine} в программе, {theirs} в отчёте',

        'warn.no_sheet_count': 'не найдено объявление SHEET_COUNT — тираж неизвестен',
        'warn.zero_sheets': 'SHEET_COUNT=0 — программа не даёт деталей',
        'warn.block_skipped': 'блок PART_DATA №{index} пропущен: нет {field}',
        'warn.only_scrap': 'в программе только служебные контуры, деталей нет',
        'warn.encoding': 'файл прочитан как {encoding}',
        'warn.no_programs': 'в папке нет файлов программ ({suffixes})',
        'warn.fms_no_sheets': 'в отчёте нет NUMBER OF SHEETS',
        'warn.fms_no_section': 'в отчёте нет секции {section}',

        'ui.shift': ' Сменное задание ',
        'ui.choose_dir': 'Выбрать папку с программами…',
        'ui.no_dir': 'папка не выбрана',
        'ui.reload': 'Перечитать',
        'ui.show': 'Показывать:',
        'ui.only_all': 'все',
        'ui.only_done': 'готовые',
        'ui.only_work': 'в работе',
        'ui.search': 'Поиск позиции:',
        'ui.warnings': 'Замечания',
        'ui.warnings_n': 'Замечания ({count})',
        'ui.export': 'Выгрузить в CSV…',
        'ui.language': 'Язык:',
        'ui.mode': 'Показ:',
        'ui.mode_parts': 'по деталям',
        'ui.mode_programs': 'по программам',
        'ui.search_parts': 'Деталь:',
        'ui.search_programs': 'Программа:',
        'ui.hint_parts': ('Двойной щелчок по детали — программы, в которых она есть. '
                          'Отметки выполнения ставятся в режиме «по программам».'),
        'ui.hint_programs': ('Щелчок по колонке с галочкой отмечает программу, '
                             'с Shift — все до неё. Двойной щелчок по строке '
                             'открывает карту наладки.'),

        'detail.title': '{part} — {total} шт, крайняя УП {last}',
        'detail.summary': 'Всего {total} шт в {count} программах, закрывается на {last}',
        'detail.close': 'Закрыть',

        'done.ambiguous': ('Под «{text}» подходит несколько программ: {names}.\n\n'
                           'Введите место в задании или более длинную часть имени.'),
        'done.unknown': ('Под «{text}» не нашлось ни одной программы.\n\n'
                         'Введите её место в задании или имя.'),

        'doc.missing': 'Рядом с программой {program} карты наладки нет.',
        'doc.failed': 'Не удалось открыть карту наладки.\n\n{error}',

        'dlg.choose_dir': 'Папка с управляющими программами',
        'dlg.read_failed': 'Не удалось прочитать папку.\n\n{error}',
        'dlg.no_programs': 'В папке нет пригодных программ.\n\n{details}',
        'dlg.no_programs_plain': 'Файлы управляющих программ не найдены.',
        'dlg.warnings': 'Замечания при разборе файлов:\n\n{items}',
        'dlg.nothing_to_export': 'Выгружать нечего: список пуст.',
        'dlg.save_as': 'Сохранить выгрузку',
        'dlg.default_name': 'готовность.csv',
        'dlg.csv_files': 'Таблица CSV',
        'dlg.all_files': 'Все файлы',
        'dlg.save_failed': 'Не удалось сохранить файл.\n\n{error}',
        'dlg.saved': 'Сохранено:\n{path}',

        'table.empty': 'Под условия отбора ничего не подошло.',
        'csv.done_programs': 'Выполнено программ:',

        'cli.description': 'Учёт готовности деталей по сменному заданию станка ЧПУ.',
        'cli.help.dir': 'папка с файлами управляющих программ',
        'cli.help.done': ('номер последней выполненной программы; '
                          'без него смена считается не начатой'),
        'cli.help.search': 'показать только позиции, содержащие текст',
        'cli.help.only': 'какие строки показывать (по умолчанию all)',
        'cli.help.mode': 'список позиций или программ (по умолчанию parts)',
        'cli.help.sort': 'сортировать по колонке ({choices})',
        'cli.help.desc': 'сортировать по убыванию',
        'cli.error.sort': ('Ошибка: в этом режиме нельзя сортировать по «{value}».\n'
                           'Доступно: {choices}'),
        'cli.help.validate': 'сверить разбор с отчётами наладки .fms',
        'cli.help.json': 'вывод в JSON вместо таблицы',
        'cli.help.lang': 'язык интерфейса ({choices})',
        'cli.error': 'Ошибка: {message}',
        'cli.error.no_programs': 'Ошибка: в папке нет пригодных программ.',
        'cli.check.clean': 'Сверка с отчётами наладки: {checked} программ, расхождений нет.',
        'cli.check.mismatches': 'Сверка с отчётами наладки: расхождений {count}.',
        'cli.notes': 'Замечания при разборе:',

        'error.not_a_directory': 'нет такой папки: {path}',
        'error.unreadable': 'не удалось прочитать файл: {details}',
    },
}

_current = FALLBACK


def available() -> List[str]:
    """Коды языков, для которых есть словарь."""
    return sorted(CATALOGS)


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def current() -> str:
    return _current


def set_language(code: Optional[str]) -> str:
    """Выбрать язык. Неизвестный код молча заменяется запасным."""
    global _current
    if code:
        code = code.strip().lower().replace('-', '_').split('_')[0]
    _current = code if code in CATALOGS else FALLBACK
    return _current


def detect() -> str:
    """Язык системы.

    Переменные окружения работают везде; на Windows они обычно не заданы,
    поэтому дальше спрашиваем саму систему. locale сознательно не трогаем:
    getdefaultlocale помечен устаревшим, а поведение у него разное по версиям.
    """
    for name in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        value = os.environ.get(name)
        if value and value not in ('C', 'POSIX'):
            code = value.split(':')[0].split('.')[0].split('_')[0].lower()
            if code in CATALOGS:
                return code

    try:
        from ctypes import windll
        # 0x419 — русский; берём только первичный язык.
        primary = windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        if primary == 0x19:
            return 'ru'
        return 'en'
    except Exception:
        return FALLBACK


def t(key: str, **params: object) -> str:
    """Перевести ключ. Неизвестный ключ возвращается как есть — заметно в UI."""
    catalog = CATALOGS.get(_current, {})
    template = catalog.get(key)
    if template is None:
        template = CATALOGS[FALLBACK].get(key, key)
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template
