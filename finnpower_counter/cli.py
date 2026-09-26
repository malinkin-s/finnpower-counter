# -*- coding: utf-8 -*-
"""Консольный интерфейс.

Средство разработки и проверки: гонять ядро на папке с заданием, не поднимая
GUI. Рабочая версия для цеха — графическая, см. finnpower_counter/gui.py.

Коды возврата:
    0 — расчёт выполнен, замечаний нет
    1 — выполнить не удалось
    2 — расчёт выполнен, но есть замечания или расхождения при сверке
"""

import argparse
import json
import sys
from typing import List, Optional

from . import presentation
from .core import balance
from .core.model import PartStatus, ShiftSummary
from .core.syntax import DEFAULT_SYNTAX

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_WARNINGS = 2

COLUMNS = presentation.COLUMNS


def _write(stream, text):
    """Печать с оглядкой на кодировку консоли.

    Консоль Windows 7 — cp866, и кириллица в ней может не пройти. Ронять
    расчёт из-за вывода нельзя.
    """
    try:
        stream.write(text + '\n')
    except UnicodeEncodeError:
        encoding = getattr(stream, 'encoding', None) or 'ascii'
        stream.write(text.encode(encoding, 'replace').decode(encoding) + '\n')


def _table(statuses: List[PartStatus]) -> List[str]:
    rows = presentation.rows(statuses)
    widths = [len(head) for head in COLUMNS]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells):
        parts = [cells[0].ljust(widths[0])]
        parts += [cells[i].rjust(widths[i]) for i in (1, 2, 3)]
        parts.append(cells[4].ljust(widths[4]))
        return '  '.join(parts).rstrip()

    out = [line(list(COLUMNS)), '  '.join('-' * w for w in widths)]
    out += [line(row) for row in rows]
    return out


def _as_json(summary: ShiftSummary,
             statuses: List[PartStatus],
             check: Optional[object]) -> str:
    payload = {
        'programs': len(summary.usable_programs),
        'unique_parts': summary.unique_parts,
        'total_pieces': summary.total_pieces,
        'warnings': summary.warnings,
        'parts': [{'part': s.part,
                   'total': s.total,
                   'last_program': s.last_program,
                   'produced': s.produced,
                   'remaining': s.remaining,
                   'complete': s.is_complete}
                  for s in statuses],
    }
    if check is not None:
        payload['cross_check'] = {
            'checked': check.checked,
            'skipped': check.skipped,
            'mismatches': check.mismatches,
        }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def build_parser():
    parser = argparse.ArgumentParser(
        prog='finnpower-counter',
        description='Учёт готовности деталей по сменному заданию станка ЧПУ.')
    parser.add_argument('-d', '--dir', required=True, metavar='ПАПКА',
                        help='папка с файлами управляющих программ')
    parser.add_argument('-n', '--done', type=int, metavar='НОМЕР',
                        help='номер последней выполненной программы; '
                             'без него смена считается не начатой')
    parser.add_argument('-s', '--search', metavar='ТЕКСТ',
                        help='показать только позиции, содержащие текст')
    parser.add_argument('--only', choices=presentation.ONLY_CHOICES, default='all',
                        help='какие позиции показывать (по умолчанию all)')
    parser.add_argument('--validate', action='store_true',
                        help='сверить разбор с отчётами наладки .fms')
    parser.add_argument('--json', action='store_true',
                        help='вывод в JSON вместо таблицы')
    return parser


def main(argv: Optional[List[str]] = None,
         stdout: Optional[object] = None,
         stderr: Optional[object] = None) -> int:
    args = build_parser().parse_args(argv)
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr

    try:
        summary = balance.load_shift(args.dir, DEFAULT_SYNTAX)
    except (NotADirectoryError, OSError) as exc:
        _write(err, 'Ошибка: {}'.format(exc))
        return EXIT_ERROR

    if not summary.parts:
        _write(err, 'Ошибка: в папке нет пригодных программ.')
        for warning in summary.warnings:
            _write(err, '  {}'.format(warning))
        return EXIT_ERROR

    statuses = balance.status_at(summary, args.done)
    shown = presentation.filter_statuses(statuses, args.only, args.search)

    check = balance.cross_check(summary.programs, DEFAULT_SYNTAX) if args.validate else None

    if args.json:
        _write(out, _as_json(summary, shown, check))
    else:
        _write(out, 'Программ: {}   Позиций: {}   Деталей: {}'.format(
            len(summary.usable_programs), summary.unique_parts, summary.total_pieces))
        _write(out, 'Выполнено программ: {}'.format(
            args.done if args.done is not None else 'смена не начата'))
        _write(out, '')
        if shown:
            for row in _table(shown):
                _write(out, row)
        else:
            _write(out, 'Под условия отбора ничего не подошло.')
        _write(out, '')
        done_count = sum(1 for s in statuses if s.is_complete)
        _write(out, 'Готово полностью: {} из {}'.format(done_count, len(statuses)))

        if check is not None:
            _write(out, '')
            if check.is_clean:
                _write(out, 'Сверка с отчётами наладки: {} программ, расхождений нет.'
                            .format(check.checked))
            elif check.checked == 0:
                _write(out, 'Сверка: отчёты наладки не найдены.')
            else:
                _write(out, 'Сверка с отчётами наладки: расхождений {}.'
                            .format(len(check.mismatches)))
                for text in check.mismatches:
                    _write(out, '  {}'.format(text))
            if check.skipped:
                _write(out, 'Без отчёта наладки: {} программ.'.format(check.skipped))

        if summary.warnings:
            _write(out, '')
            _write(out, 'Замечания при разборе:')
            for warning in summary.warnings:
                _write(out, '  {}'.format(warning))

    if summary.warnings or (check is not None and check.mismatches):
        return EXIT_WARNINGS
    return EXIT_OK


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
