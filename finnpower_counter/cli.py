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

from . import i18n, presentation
from .core import balance
from .core.model import PartStatus, ShiftSummary
from .core.syntax import DEFAULT_SYNTAX

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_WARNINGS = 2

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
    head = presentation.columns()
    rows = presentation.rows(statuses)
    widths = [len(cell) for cell in head]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def line(cells):
        parts = [cells[0].ljust(widths[0])]
        parts += [cells[i].rjust(widths[i]) for i in (1, 2, 3)]
        parts.append(cells[4].ljust(widths[4]))
        return '  '.join(parts).rstrip()

    out = [line(head), '  '.join('-' * w for w in widths)]
    out += [line(row) for row in rows]
    return out


def _as_json(summary: ShiftSummary,
             statuses: List[PartStatus],
             check: Optional[object]) -> str:
    payload = {
        'programs': len(summary.usable_programs),
        'unique_parts': summary.unique_parts,
        'total_pieces': summary.total_pieces,
        'warnings': [str(note) for note in summary.warnings],
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
            'mismatches': [str(note) for note in check.mismatches],
        }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _preferred_language(argv: Optional[List[str]]) -> str:
    """Язык из --lang, иначе из системы."""
    items = list(sys.argv[1:] if argv is None else argv)
    for index, item in enumerate(items):
        if item == '--lang' and index + 1 < len(items):
            return items[index + 1]
        if item.startswith('--lang='):
            return item.split('=', 1)[1]
    return i18n.detect()


def build_parser():
    parser = argparse.ArgumentParser(
        prog='finnpower-counter',
        description=i18n.t('cli.description'))
    parser.add_argument('-d', '--dir', required=True, metavar='DIR',
                        help=i18n.t('cli.help.dir'))
    parser.add_argument('-n', '--done', type=int, metavar='N',
                        help=i18n.t('cli.help.done'))
    parser.add_argument('-s', '--search', metavar='TEXT',
                        help=i18n.t('cli.help.search'))
    parser.add_argument('--only', choices=presentation.ONLY_CHOICES, default='all',
                        help=i18n.t('cli.help.only'))
    parser.add_argument('--validate', action='store_true',
                        help=i18n.t('cli.help.validate'))
    parser.add_argument('--json', action='store_true',
                        help=i18n.t('cli.help.json'))
    parser.add_argument('--lang', choices=i18n.available(),
                        help=i18n.t('cli.help.lang',
                                    choices='/'.join(i18n.available())))
    return parser


def main(argv: Optional[List[str]] = None,
         stdout: Optional[object] = None,
         stderr: Optional[object] = None) -> int:
    # Язык нужен до сборки парсера: иначе справка выйдет не на том языке.
    i18n.set_language(_preferred_language(argv))
    args = build_parser().parse_args(argv)
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr

    try:
        summary = balance.load_shift(args.dir, DEFAULT_SYNTAX)
    except (NotADirectoryError, OSError) as exc:
        _write(err, i18n.t('cli.error', message=exc))
        return EXIT_ERROR

    if not summary.parts:
        _write(err, i18n.t('cli.error.no_programs'))
        for warning in summary.warnings:
            _write(err, '  {}'.format(warning))
        return EXIT_ERROR

    statuses = balance.status_at(summary, args.done)
    shown = presentation.filter_statuses(statuses, args.only, args.search)

    check = balance.cross_check(summary.programs, DEFAULT_SYNTAX) if args.validate else None

    if args.json:
        _write(out, _as_json(summary, shown, check))
    else:
        _write(out, presentation.counters(summary, statuses))
        _write(out, i18n.t(
            'programs.done',
            value=args.done if args.done is not None
            else i18n.t('programs.not_started')))
        _write(out, '')
        if shown:
            for row in _table(shown):
                _write(out, row)
        else:
            _write(out, i18n.t('table.empty'))
        _write(out, '')
        if check is not None:
            _write(out, '')
            if check.is_clean:
                _write(out, i18n.t('cli.check.clean', checked=check.checked))
            elif check.checked == 0:
                _write(out, i18n.t('check.not_found'))
            else:
                _write(out, i18n.t('cli.check.mismatches',
                                   count=len(check.mismatches)))
                for note in check.mismatches:
                    _write(out, '  {}'.format(note))
            if check.skipped:
                _write(out, i18n.t('check.skipped_line', count=check.skipped))

        if summary.warnings:
            _write(out, '')
            _write(out, i18n.t('cli.notes'))
            for warning in summary.warnings:
                _write(out, '  {}'.format(warning))

    if summary.warnings or (check is not None and check.mismatches):
        return EXIT_WARNINGS
    return EXIT_OK


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
