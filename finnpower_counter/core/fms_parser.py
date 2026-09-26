# -*- coding: utf-8 -*-
"""Разбор отчёта наладки (.fms).

Отчёт нужен не для учёта, а для сверки. Он содержит те же числа, что и
управляющая программа, но записанные независимо и в двух видах: секция
#RSCUT — сразу сумма по детали, секция #COMPONENTS — построчно по каждому
блоку. Совпадение трёх источников означает, что разбор .nc верен.
"""

import os
from typing import Dict, List, Optional

from . import reader
from .model import ProgramNest
from .syntax import DEFAULT_SYNTAX, FMS_SECTIONS, MachineSyntax


def _section(text, marker):
    # type: (str, str) -> str
    """Текст от маркера секции до следующего маркера верхнего уровня."""
    if marker not in text:
        return ''
    tail = text.split(marker, 1)[1]
    lines = []
    for line in tail.splitlines():
        if line.startswith('#'):
            break
        lines.append(line)
    return '\n'.join(lines)


def parse_text(text, name, path='', number=None, syntax=DEFAULT_SYNTAX):
    # type: (str, str, str, Optional[int], MachineSyntax) -> ProgramNest
    text = reader.normalize_newlines(text)
    warnings = []  # type: List[str]

    match = syntax.fms_sheet_count.search(text)
    if match is None:
        sheet_count = None
        warnings.append('в отчёте нет NUMBER OF SHEETS')
    else:
        sheet_count = int(match.group(1))

    parts = {}  # type: Dict[str, int]
    rscut = _section(text, FMS_SECTIONS['rscut'])
    for part, qty in syntax.fms_rscut_part.findall(rscut):
        if syntax.is_scrap(part):
            continue
        parts[part] = parts.get(part, 0) + int(qty)
    if not rscut:
        warnings.append('в отчёте нет секции {}'.format(FMS_SECTIONS['rscut']))

    return ProgramNest(
        number=number if number is not None else -1,
        name=name,
        path=path,
        sheet_count=sheet_count,
        parts_per_sheet=parts,
        warnings=warnings,
    )


def parse_components(text, syntax=DEFAULT_SYNTAX):
    # type: (str, MachineSyntax) -> Dict[str, int]
    """Количества из секции #COMPONENTS — построчно по блокам, затем сумма."""
    text = reader.normalize_newlines(text)
    parts = {}  # type: Dict[str, int]
    section = _section(text, FMS_SECTIONS['components'])
    for part, qty in syntax.fms_component_part.findall(section):
        if syntax.is_scrap(part):
            continue
        parts[part] = parts.get(part, 0) + int(qty)
    return parts


def parse_file(path, syntax=DEFAULT_SYNTAX):
    # type: (str, MachineSyntax) -> ProgramNest
    text, _ = reader.read_text(path, syntax)
    name = os.path.splitext(os.path.basename(path))[0]
    return parse_text(text, name=name, path=path,
                      number=reader.program_number(path, syntax), syntax=syntax)


def find_report(nc_path, syntax=DEFAULT_SYNTAX):
    # type: (str, MachineSyntax) -> Optional[str]
    """Найти отчёт наладки рядом с программой."""
    stem = os.path.splitext(nc_path)[0]
    for suffix in syntax.fms_suffixes:
        for candidate in (stem + suffix, stem + suffix.upper()):
            if os.path.isfile(candidate):
                return candidate
    return None
