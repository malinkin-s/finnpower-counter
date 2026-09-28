# -*- coding: utf-8 -*-
"""Подготовка данных к показу: отбор, строки таблицы, выгрузка.

Общее для консоли и окна. Вынесено из обоих, чтобы правила отбора, состав
колонок и подписи были в одном месте и проверялись тестами без поднятия окна.

Подписи берутся из i18n в момент вызова, а не при загрузке модуля: язык может
смениться уже после того, как окно построено.
"""

import csv
import io
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from . import i18n
from .core.model import CrossCheckResult, PartStatus, PartTotal, ProgramNest, ShiftSummary

# Режимы показа: по позициям или по управляющим программам.
MODE_PARTS = 'parts'
MODE_PROGRAMS = 'programs'
MODES = (MODE_PARTS, MODE_PROGRAMS)

# Устойчивые обозначения колонок. Порядок задаёт порядок в таблице и в CSV.
COLUMN_KEYS = ('col.part', 'col.total', 'col.last_program',
               'col.produced', 'col.status')
PROGRAM_COLUMN_KEYS = ('col.mark', 'col.program', 'col.sheet_size', 'col.sheets',
                       'col.positions', 'col.pieces', 'col.status')

# Отметка выполнения. Вынесена в константы: если на цеховой машине галочка
# не отрисуется, её меняют здесь, не трогая остальной код.
MARK_DONE = '\u2713'
MARK_NONE = ''

# Указатель направления сортировки в заголовке колонки.
ARROW_UP = ' \u25b2'
ARROW_DOWN = ' \u25bc'
# Колонки окна отдельной позиции.
DETAIL_COLUMN_KEYS = ('col.program', 'col.sheets', 'col.per_sheet',
                      'col.in_program', 'col.cumulative')

# Выравнивание колонок: 'l' — по левому краю, 'r' — по правому, 'c' — центр.
# Числа вправо, обозначения и статусы влево, размер листа — как текст.
COLUMN_ALIGN = {
    MODE_PARTS: ('l', 'r', 'r', 'r', 'l'),
    MODE_PROGRAMS: ('c', 'l', 'l', 'r', 'r', 'r', 'l'),
}
DETAIL_ALIGN = ('l', 'r', 'r', 'r', 'r')


def align(mode: str = MODE_PARTS) -> Sequence[str]:
    return COLUMN_ALIGN.get(mode, COLUMN_ALIGN[MODE_PARTS])

ONLY_ALL = 'all'
ONLY_DONE = 'done'
ONLY_WORK = 'work'
ONLY_CHOICES = (ONLY_ALL, ONLY_DONE, ONLY_WORK)


def column_keys(mode: str = MODE_PARTS) -> Sequence[str]:
    return PROGRAM_COLUMN_KEYS if mode == MODE_PROGRAMS else COLUMN_KEYS


def columns(mode: str = MODE_PARTS) -> List[str]:
    """Подписи колонок на текущем языке."""
    return [i18n.t(key) for key in column_keys(mode)]


def detail_columns() -> List[str]:
    return [i18n.t(key) for key in DETAIL_COLUMN_KEYS]


def status_text(status: PartStatus) -> str:
    """Подпись статуса: 'Готово' / 'В работе' или их перевод."""
    return i18n.t('status.' + status.status)


def filter_statuses(statuses: Iterable[PartStatus],
                    only: str = ONLY_ALL,
                    search: Optional[str] = None) -> List[PartStatus]:
    """Отобрать позиции для показа.

    Отбор влияет только на показ. Итоговые цифры готовности считаются по всей
    смене — иначе оператор, отфильтровав список, увидит неверный баланс.
    """
    result = list(statuses)
    if only == ONLY_DONE:
        result = [s for s in result if s.is_complete]
    elif only == ONLY_WORK:
        result = [s for s in result if not s.is_complete]
    if search:
        needle = search.strip().lower()
        if needle:
            result = [s for s in result if needle in s.part.lower()]
    return result


def row(status: PartStatus) -> List[str]:
    return [status.part,
            str(status.total),
            status.last_program,
            '{} / {}'.format(status.produced, status.total),
            status_text(status)]


def rows(statuses: Iterable[PartStatus]) -> List[List[str]]:
    return [row(s) for s in statuses]


def is_executed(nest: ProgramNest, done: Iterable[int] = ()) -> bool:
    return nest.position in set(done)


def program_row(nest: ProgramNest, done: Iterable[int] = ()) -> List[str]:
    executed = is_executed(nest, done)
    return [MARK_DONE if executed else MARK_NONE,
            nest.name,
            nest.sheet_size or '—',
            '—' if nest.sheet_count is None else str(nest.sheet_count),
            str(nest.unique_parts),
            str(nest.total_pieces),
            i18n.t('status.executed' if executed else 'status.pending')]


def program_rows(programs: Iterable[ProgramNest],
                 done: Iterable[int] = ()) -> List[List[str]]:
    places = set(done)
    return [program_row(nest, places) for nest in programs]


def filter_programs(programs: Iterable[ProgramNest],
                    only: str = ONLY_ALL,
                    search: Optional[str] = None,
                    done: Iterable[int] = ()) -> List[ProgramNest]:
    """Отобрать программы для показа.

    В этом режиме «готово» означает «программа выполнена».

    Поиск: цифры, совпавшие с местом в задании, дают ровно эту программу —
    иначе ввод «1» вытаскивал бы заодно PRG_10, PRG_11 и PRG_12. Если такого
    места нет, цифры ищутся как подстрока: в именах вида 000102zz201001
    оператор ищет именно куском имени.
    """
    result = list(programs)
    places = set(done)
    if only == ONLY_DONE:
        result = [p for p in result if p.position in places]
    elif only == ONLY_WORK:
        result = [p for p in result if p.position not in places]
    if search:
        needle = search.strip().lower()
        if needle.isdecimal() and any(p.position == int(needle) for p in result):
            place = int(needle)
            result = [p for p in result if p.position == place]
        elif needle:
            result = [p for p in result if needle in p.name.lower()]
    return result


def part_detail_rows(part: PartTotal,
                     programs: Iterable[ProgramNest]) -> List[List[str]]:
    """Построчная выработка одной позиции по программам, с накоплением.

    Накопительный столбец отвечает на вопрос оператора «сколько будет
    в сумме, когда отработает эта программа».
    """
    by_place = {nest.position: nest for nest in programs}
    running = 0
    result = []
    for place in sorted(part.by_program):
        count = part.by_program[place]
        running += count
        nest = by_place.get(place)
        result.append([
            nest.name if nest else str(place),
            '—' if nest is None or nest.sheet_count is None else str(nest.sheet_count),
            str(nest.parts_per_sheet.get(part.part, '—')) if nest else '—',
            str(count),
            '{} / {}'.format(running, part.total),
        ])
    return result


def counters(summary: ShiftSummary, statuses: Sequence[PartStatus]) -> str:
    """Строка с итогами смены."""
    return i18n.t('counters',
                  programs=len(summary.usable_programs),
                  parts=summary.unique_parts,
                  pieces=summary.total_pieces,
                  done=sum(1 for s in statuses if s.is_complete),
                  total=len(statuses))


def cross_check_line(result: Optional[CrossCheckResult]) -> str:
    """Строка о сверке с отчётами наладки."""
    if result is None:
        return i18n.t('check.none')
    if result.checked == 0:
        return i18n.t('check.not_found')
    if result.mismatches:
        return i18n.t('check.mismatches',
                      count=len(result.mismatches), checked=result.checked)
    line = i18n.t('check.clean', checked=result.checked)
    if result.skipped:
        line += i18n.t('check.skipped', count=result.skipped)
    return line


# Сортировка идёт по данным, а не по тому, что напечатано в ячейке:
# «Крайняя УП» показывает имя, а упорядочивать её надо по месту в задании.
PART_SORT_KEYS: Dict[str, Callable] = {
    'col.part': lambda s: s.part,
    'col.total': lambda s: s.total,
    'col.last_program': lambda s: s.last_position,
    'col.produced': lambda s: s.produced,
    'col.status': lambda s: s.is_complete,
}


def sort_statuses(statuses: Iterable[PartStatus],
                  column: Optional[str] = None,
                  reverse: bool = False) -> List[PartStatus]:
    """Упорядочить позиции. Без колонки — по артикулу."""
    items = list(statuses)
    key = PART_SORT_KEYS.get(column or '')
    if key is None:
        return sorted(items, key=lambda s: s.part, reverse=reverse)
    # Артикул вторым ключом, иначе равные значения встают как попало.
    return sorted(items, key=lambda s: (key(s), s.part), reverse=reverse)


def program_sort_keys(done: Iterable[int] = ()) -> Dict[str, Callable]:
    places = set(done)
    return {
        'col.mark': lambda n: n.position in places,
        'col.program': lambda n: n.name.lower(),
        'col.sheet_size': lambda n: (n.sheet_x or 0) * (n.sheet_y or 0),
        'col.sheets': lambda n: n.sheet_count or 0,
        'col.positions': lambda n: n.unique_parts,
        'col.pieces': lambda n: n.total_pieces,
        'col.status': lambda n: n.position in places,
    }


def sort_programs(programs: Iterable[ProgramNest],
                  column: Optional[str] = None,
                  reverse: bool = False,
                  done: Iterable[int] = ()) -> List[ProgramNest]:
    """Упорядочить программы. Без колонки — по месту в задании."""
    items = list(programs)
    key = program_sort_keys(done).get(column or '')
    if key is None:
        return sorted(items, key=lambda n: n.position, reverse=reverse)
    return sorted(items, key=lambda n: (key(n), n.position), reverse=reverse)


def sortable(mode: str, column: str) -> bool:
    keys = PART_SORT_KEYS if mode == MODE_PARTS else program_sort_keys()
    return column in keys


def sort_choices() -> List[str]:
    """Короткие имена колонок для консоли: col.total -> total."""
    keys = list(COLUMN_KEYS) + list(PROGRAM_COLUMN_KEYS)
    seen = []
    for key in keys:
        short = key.split('.', 1)[1]
        if short not in seen:
            seen.append(short)
    return seen


def sort_column(mode: str, short: Optional[str]) -> Optional[str]:
    """Найти колонку режима по короткому имени."""
    if not short:
        return None
    key = 'col.' + short.strip().lower()
    return key if sortable(mode, key) else None


def heading(column: str, active: Optional[str], reverse: bool) -> str:
    """Подпись колонки со стрелкой, если сортировка идёт по ней."""
    title = i18n.t(column)
    if column != active:
        return title
    return title + (ARROW_DOWN if reverse else ARROW_UP)


def to_csv(statuses: Iterable[PartStatus],
           done_count: Optional[int] = None,
           delimiter: str = ';') -> str:
    """Выгрузка для маршрутного листа.

    Разделитель ";" — так русский Excel открывает файл без мастера импорта.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator='\r\n')
    if done_count is not None:
        writer.writerow([i18n.t('csv.done_programs'), done_count])
    writer.writerow(columns(MODE_PARTS))
    for status in statuses:
        writer.writerow(row(status))
    return buffer.getvalue()


def write_csv(path: str,
              statuses: Iterable[PartStatus],
              done_count: Optional[int] = None) -> None:
    """Записать выгрузку. utf-8 с BOM — иначе Excel портит кириллицу."""
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        fh.write(to_csv(statuses, done_count))
