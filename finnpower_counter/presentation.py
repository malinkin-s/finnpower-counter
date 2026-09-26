# -*- coding: utf-8 -*-
"""Подготовка данных к показу: отбор, строки таблицы, выгрузка.

Общее для консоли и окна. Вынесено из обоих, чтобы правила отбора и состав
колонок были в одном месте и проверялись тестами без поднятия окна.
"""

import csv
import io
from typing import Iterable, List, Optional, Sequence

from .core.model import PartStatus, ShiftSummary

COLUMNS = ('Артикул', 'Всего в заказе', 'Крайняя УП', 'Готово сейчас', 'Статус')

ONLY_ALL = 'all'
ONLY_DONE = 'done'
ONLY_WORK = 'work'
ONLY_CHOICES = (ONLY_ALL, ONLY_DONE, ONLY_WORK)


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
            status.status]


def rows(statuses: Iterable[PartStatus]) -> List[List[str]]:
    return [row(s) for s in statuses]


def counters(summary: ShiftSummary, statuses: Sequence[PartStatus]) -> str:
    """Строка с итогами смены."""
    done = sum(1 for s in statuses if s.is_complete)
    return ('Программ: {}    Позиций: {}    Деталей: {}    '
            'Готово полностью: {} из {}').format(
        len(summary.usable_programs), summary.unique_parts,
        summary.total_pieces, done, len(statuses))


def cross_check_line(result: Optional[object]) -> str:
    """Строка о сверке с отчётами наладки."""
    if result is None:
        return 'Сверка не выполнялась'
    if result.checked == 0:
        return 'Сверка: отчёты наладки не найдены'
    if result.mismatches:
        return 'Сверка: расхождений {} в {} отчётах'.format(
            len(result.mismatches), result.checked)
    line = 'Сверено с {} отчётами наладки, расхождений нет'.format(result.checked)
    if result.skipped:
        line += ' (без отчёта: {})'.format(result.skipped)
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
        writer.writerow(['Выполнено программ:', done_program])
    writer.writerow(list(COLUMNS))
    for status in statuses:
        writer.writerow(row(status))
    return buffer.getvalue()


def write_csv(path: str,
              statuses: Iterable[PartStatus],
              done_program: Optional[int] = None) -> None:
    """Записать выгрузку. utf-8 с BOM — иначе Excel портит кириллицу."""
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        fh.write(to_csv(statuses, done_program))
