# -*- coding: utf-8 -*-
"""Подготовка данных к показу: отбор, строки таблицы, выгрузка.

Общее для консоли и окна. Вынесено из обоих, чтобы правила отбора, состав
колонок и подписи были в одном месте и проверялись тестами без поднятия окна.

Подписи берутся из i18n в момент вызова, а не при загрузке модуля: язык может
смениться уже после того, как окно построено.
"""

import csv
import io
from typing import Iterable, List, Optional, Sequence

from . import i18n
from .core.model import CrossCheckResult, PartStatus, PartTotal, ProgramNest, ShiftSummary

# Режимы показа: по позициям или по управляющим программам.
MODE_PARTS = 'parts'
MODE_PROGRAMS = 'programs'
MODES = (MODE_PARTS, MODE_PROGRAMS)

# Устойчивые обозначения колонок. Порядок задаёт порядок в таблице и в CSV.
COLUMN_KEYS = ('col.part', 'col.total', 'col.last_program',
               'col.produced', 'col.status')
PROGRAM_COLUMN_KEYS = ('col.program', 'col.sheet_size', 'col.sheets',
                       'col.positions', 'col.pieces', 'col.status')
# Колонки окна отдельной позиции.
DETAIL_COLUMN_KEYS = ('col.program', 'col.sheets', 'col.per_sheet',
                      'col.in_program', 'col.cumulative')

# Выравнивание колонок: 'l' — по левому краю, 'r' — по правому, 'c' — центр.
# Числа вправо, обозначения и статусы влево, размер листа — как текст.
COLUMN_ALIGN = {
    MODE_PARTS: ('l', 'r', 'r', 'r', 'l'),
    MODE_PROGRAMS: ('l', 'l', 'r', 'r', 'r', 'l'),
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
            str(status.last_program),
            '{} / {}'.format(status.produced, status.total),
            status_text(status)]


def rows(statuses: Iterable[PartStatus]) -> List[List[str]]:
    return [row(s) for s in statuses]


def program_row(nest: ProgramNest, done: Optional[int] = None) -> List[str]:
    executed = done is not None and nest.number <= done
    return [nest.name,
            nest.sheet_size or '—',
            '—' if nest.sheet_count is None else str(nest.sheet_count),
            str(nest.unique_parts),
            str(nest.total_pieces),
            i18n.t('status.executed' if executed else 'status.pending')]


def program_rows(programs: Iterable[ProgramNest],
                 done: Optional[int] = None) -> List[List[str]]:
    return [program_row(nest, done) for nest in programs]


def filter_programs(programs: Iterable[ProgramNest],
                    only: str = ONLY_ALL,
                    search: Optional[str] = None,
                    done: Optional[int] = None) -> List[ProgramNest]:
    """Отобрать программы для показа.

    В этом режиме «готово» означает «программа выполнена».

    Поиск: если введены одни цифры — это номер программы, и совпадение
    точное. Иначе подстрока в имени. Без этого разделения ввод «1» вытаскивал
    бы заодно PRG_10, PRG_11 и PRG_12, что оператору только мешает.
    """
    result = list(programs)
    if only == ONLY_DONE:
        result = [p for p in result if done is not None and p.number <= done]
    elif only == ONLY_WORK:
        result = [p for p in result if done is None or p.number > done]
    if search:
        needle = search.strip().lower()
        if needle.isdigit():
            number = int(needle)
            result = [p for p in result if p.number == number]
        elif needle:
            result = [p for p in result if needle in p.name.lower()]
    return result


def part_detail_rows(part: PartTotal,
                     programs: Iterable[ProgramNest]) -> List[List[str]]:
    """Построчная выработка одной позиции по программам, с накоплением.

    Накопительный столбец отвечает на вопрос оператора «сколько будет
    в сумме, когда отработает эта программа».
    """
    by_number = {nest.number: nest for nest in programs}
    running = 0
    result = []
    for number in sorted(part.by_program):
        count = part.by_program[number]
        running += count
        nest = by_number.get(number)
        result.append([
            nest.name if nest else str(number),
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


def to_csv(statuses: Iterable[PartStatus],
           done_program: Optional[int] = None,
           delimiter: str = ';') -> str:
    """Выгрузка для маршрутного листа.

    Разделитель ";" — так русский Excel открывает файл без мастера импорта.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator='\r\n')
    if done_program is not None:
        writer.writerow([i18n.t('csv.done_programs'), done_program])
    writer.writerow(columns(MODE_PARTS))
    for status in statuses:
        writer.writerow(row(status))
    return buffer.getvalue()


def write_csv(path: str,
              statuses: Iterable[PartStatus],
              done_program: Optional[int] = None) -> None:
    """Записать выгрузку. utf-8 с BOM — иначе Excel портит кириллицу."""
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        fh.write(to_csv(statuses, done_program))
