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
from .core.model import CrossCheckResult, PartStatus, ShiftSummary

# Устойчивые обозначения колонок. Порядок задаёт порядок в таблице и в CSV.
COLUMN_KEYS = ('col.part', 'col.total', 'col.last_program',
               'col.produced', 'col.status')

ONLY_ALL = 'all'
ONLY_DONE = 'done'
ONLY_WORK = 'work'
ONLY_CHOICES = (ONLY_ALL, ONLY_DONE, ONLY_WORK)


def columns() -> List[str]:
    """Подписи колонок на текущем языке."""
    return [i18n.t(key) for key in COLUMN_KEYS]


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
    writer.writerow(columns())
    for status in statuses:
        writer.writerow(row(status))
    return buffer.getvalue()


def write_csv(path: str,
              statuses: Iterable[PartStatus],
              done_program: Optional[int] = None) -> None:
    """Записать выгрузку. utf-8 с BOM — иначе Excel портит кириллицу."""
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        fh.write(to_csv(statuses, done_program))
