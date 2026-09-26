# -*- coding: utf-8 -*-
"""Свод смены и сверка с отчётами наладки."""

import os
from typing import Dict, List, Optional

from . import fms_parser, nc_parser, reader
from .model import (CrossCheckResult, PartStatus, PartTotal, ProgramNest,
                    ShiftSummary)
from .syntax import DEFAULT_SYNTAX, MachineSyntax


def summarize(programs):
    # type: (List[ProgramNest]) -> ShiftSummary
    """Свести тираж по позициям за смену.

    Обход строго по возрастанию номера программы: крайняя программа позиции —
    это последняя по порядку выполнения, а не последняя по алфавиту имени.
    """
    ordered = sorted(programs, key=lambda p: p.number)

    totals = {}  # type: Dict[str, int]
    last = {}  # type: Dict[str, int]
    by_program = {}  # type: Dict[str, Dict[int, int]]

    for nest in ordered:
        if not nest.is_usable:
            continue
        for part, count in nest.pieces().items():
            if count <= 0:
                continue
            totals[part] = totals.get(part, 0) + count
            last[part] = nest.number
            by_program.setdefault(part, {})[nest.number] = count

    parts = [PartTotal(part=part,
                       total=totals[part],
                       last_program=last[part],
                       by_program=by_program.get(part, {}))
             for part in sorted(totals)]

    warnings = []  # type: List[str]
    for nest in ordered:
        for text in nest.warnings:
            warnings.append('{}: {}'.format(nest.name, text))

    return ShiftSummary(programs=ordered, parts=parts, warnings=warnings)


def status_at(summary, done_program):
    # type: (ShiftSummary, Optional[int]) -> List[PartStatus]
    """Состояние позиций, когда выполнены все программы по номер done_program.

    done_program=None — смена ещё не начата, изготовлено ноль.
    """
    statuses = []
    for part in summary.parts:
        if done_program is None:
            produced = 0
        else:
            produced = sum(count for number, count in part.by_program.items()
                           if number <= done_program)
        statuses.append(PartStatus(part=part.part,
                                   total=part.total,
                                   last_program=part.last_program,
                                   produced=produced))
    return statuses


def cross_check(programs, syntax=DEFAULT_SYNTAX):
    # type: (List[ProgramNest], MachineSyntax) -> CrossCheckResult
    """Сверить разбор каждой программы с её отчётом наладки.

    Сверяются три независимых источника: .nc, секция #RSCUT и секция
    #COMPONENTS отчёта.
    """
    result = CrossCheckResult()

    for nest in programs:
        report = fms_parser.find_report(nest.path, syntax) if nest.path else None
        if report is None:
            result.skipped += 1
            continue

        text, _ = reader.read_text(report, syntax)
        from_rscut = fms_parser.parse_text(
            text, name=nest.name, path=report, number=nest.number, syntax=syntax)
        from_components = fms_parser.parse_components(text, syntax)

        result.checked += 1

        if nest.sheet_count != from_rscut.sheet_count:
            result.mismatches.append(
                '{}: листов в программе {}, в отчёте {}'.format(
                    nest.name, nest.sheet_count, from_rscut.sheet_count))

        for label, other in (('#RSCUT', from_rscut.parts_per_sheet),
                             ('#COMPONENTS', from_components)):
            if nest.parts_per_sheet != other:
                for part in sorted(set(nest.parts_per_sheet) | set(other)):
                    mine = nest.parts_per_sheet.get(part, 0)
                    theirs = other.get(part, 0)
                    if mine != theirs:
                        result.mismatches.append(
                            '{}: {} — в программе {}, в {} {}'.format(
                                nest.name, part, mine, label, theirs))

    return result


def load_shift(directory, syntax=DEFAULT_SYNTAX):
    # type: (str, MachineSyntax) -> ShiftSummary
    """Прочитать папку со сменным заданием и свести её."""
    if not os.path.isdir(directory):
        raise NotADirectoryError('нет такой папки: {}'.format(directory))
    programs = nc_parser.collect_programs(directory, syntax)
    summary = summarize(programs)
    if not programs:
        summary.warnings.append(
            'в папке нет файлов программ ({})'.format(
                ', '.join(syntax.nc_suffixes)))
    return summary
