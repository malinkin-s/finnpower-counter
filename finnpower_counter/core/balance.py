# -*- coding: utf-8 -*-
"""Свод смены и сверка с отчётами наладки."""

import os
from typing import Dict, List, Optional

from .. import i18n
from . import fms_parser, nc_parser, reader
from .model import (CrossCheckResult, Note, PartStatus, PartTotal,
                    ProgramNest, ShiftSummary)
from .syntax import DEFAULT_SYNTAX, MachineSyntax


def summarize(programs: List[ProgramNest]) -> ShiftSummary:
    """Свести тираж по позициям за смену.

    Обход строго по местам в задании: крайняя программа позиции — последняя
    по порядку выполнения, а не последняя по алфавиту имени и не с наибольшим
    числом в имени.
    """
    ordered = sorted(programs, key=lambda p: p.position)

    totals: Dict[str, int] = {}
    last: Dict[str, int] = {}
    last_name: Dict[str, str] = {}
    by_program: Dict[str, Dict[int, int]] = {}

    for nest in ordered:
        if not nest.is_usable:
            continue
        for part, count in nest.pieces().items():
            if count <= 0:
                continue
            totals[part] = totals.get(part, 0) + count
            last[part] = nest.position
            last_name[part] = nest.name
            by_program.setdefault(part, {})[nest.position] = count

    parts = [PartTotal(part=part,
                       total=totals[part],
                       last_position=last[part],
                       last_program=last_name[part],
                       by_program=by_program.get(part, {}))
             for part in sorted(totals)]

    warnings: List[Note] = []
    for nest in ordered:
        for note in nest.warnings:
            warnings.append(note.with_program(nest.name))

    return ShiftSummary(programs=ordered, parts=parts, warnings=warnings)


def status_at(summary: ShiftSummary, done: Optional[int]) -> List[PartStatus]:
    """Состояние позиций, когда выполнены программы по место done.

    done=None — смена ещё не начата, изготовлено ноль.
    """
    statuses = []
    for part in summary.parts:
        if done is None:
            produced = 0
        else:
            produced = sum(count for place, count in part.by_program.items()
                           if place <= done)
        statuses.append(PartStatus(part=part.part,
                                   total=part.total,
                                   last_position=part.last_position,
                                   last_program=part.last_program,
                                   produced=produced))
    return statuses


def resolve_position(summary: ShiftSummary, text: str) -> Optional[int]:
    """Понять, какую программу назвал оператор.

    Принимает три вида ввода, потому что на разных производствах программы
    называются по-разному:

    * пустая строка — смена не начата;
    * место в задании, 1..N — привычный случай, когда файлы PRG_01..PRG_30;
    * имя программы целиком или его отличимый кусок — для имён вида
      000101zz201001, где место приходится считать, а имя оператор видит
      на стойке.

    Место проверяется первым: цифры чаще означают именно его.
    """
    text = (text or '').strip()
    if not text:
        return None

    places = summary.positions
    if text.isdigit():
        place = int(text)
        if place in places:
            return place

    lowered = text.lower()
    exact = [n for n in summary.usable_programs if n.name.lower() == lowered]
    if len(exact) == 1:
        return exact[0].position

    partial = [n for n in summary.usable_programs if lowered in n.name.lower()]
    if len(partial) == 1:
        return partial[0].position
    if len(partial) > 1:
        raise ValueError(Note('done.ambiguous', {
            'text': text,
            'names': ', '.join(n.name for n in partial[:4])}))

    if text.isdigit() and places and int(text) > max(places):
        return max(places)

    raise ValueError(Note('done.unknown', {'text': text}))


def cross_check(programs: List[ProgramNest],
                syntax: MachineSyntax = DEFAULT_SYNTAX) -> CrossCheckResult:
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

        if (nest.sheet_x, nest.sheet_y) != (from_rscut.sheet_x, from_rscut.sheet_y):
            result.mismatches.append(Note('mismatch.sheet_size', {
                'program': nest.name,
                'mine': nest.sheet_size or '—',
                'theirs': from_rscut.sheet_size or '—'}))

        if nest.sheet_count != from_rscut.sheet_count:
            result.mismatches.append(Note('mismatch.sheets', {
                'program': nest.name,
                'mine': nest.sheet_count,
                'theirs': from_rscut.sheet_count}))

        for label, other in (('#RSCUT', from_rscut.parts_per_sheet),
                             ('#COMPONENTS', from_components)):
            if nest.parts_per_sheet != other:
                for part in sorted(set(nest.parts_per_sheet) | set(other)):
                    mine = nest.parts_per_sheet.get(part, 0)
                    theirs = other.get(part, 0)
                    if mine != theirs:
                        result.mismatches.append(Note('mismatch.part', {
                            'program': nest.name, 'part': part,
                            'mine': mine, 'section': label, 'theirs': theirs}))

    return result


def load_shift(directory: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> ShiftSummary:
    """Прочитать папку со сменным заданием и свести её."""
    if not os.path.isdir(directory):
        raise NotADirectoryError(
            i18n.t('error.not_a_directory', path=directory))
    programs = nc_parser.collect_programs(directory, syntax)
    summary = summarize(programs)
    if not programs:
        summary.warnings.append(Note('warn.no_programs', {
            'suffixes': ', '.join(syntax.nc_suffixes)}))
    return summary
