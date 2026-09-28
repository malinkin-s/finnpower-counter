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
from .model import Note, ProgramNest
from .syntax import DEFAULT_SYNTAX, FMS_SECTIONS, MachineSyntax


def _section(text: str, marker: str) -> str:
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


def parse_text(text: str,
               name: str,
               path: str = '',
               number: Optional[int] = None,
               syntax: MachineSyntax = DEFAULT_SYNTAX) -> ProgramNest:
    text = reader.normalize_newlines(text)
    warnings: List[Note] = []

    match = syntax.fms_sheet_count.search(text)
    if match is None:
        sheet_count = None
        warnings.append(Note('warn.fms_no_sheets'))
    else:
        sheet_count = int(match.group(1))

    parts: Dict[str, int] = {}
    rscut = _section(text, FMS_SECTIONS['rscut'])
    for part, qty in syntax.fms_rscut_part.findall(rscut):
        if syntax.is_scrap(part):
            continue
        parts[part] = parts.get(part, 0) + int(qty)
    if not rscut:
        warnings.append(Note('warn.fms_no_section',
                             {'section': FMS_SECTIONS['rscut']}))

    return ProgramNest(
        position=0,
        number=number,
        name=name,
        path=path,
        sheet_count=sheet_count,
        sheet_x=reader.search_float(syntax.fms_sheet_x, text),
        sheet_y=reader.search_float(syntax.fms_sheet_y, text),
        parts_per_sheet=parts,
        warnings=warnings,
    )


def parse_components(text: str,
                     syntax: MachineSyntax = DEFAULT_SYNTAX) -> Dict[str, int]:
    """Количества из секции #COMPONENTS — построчно по блокам, затем сумма."""
    text = reader.normalize_newlines(text)
    parts: Dict[str, int] = {}
    section = _section(text, FMS_SECTIONS['components'])
    for part, qty in syntax.fms_component_part.findall(section):
        if syntax.is_scrap(part):
            continue
        parts[part] = parts.get(part, 0) + int(qty)
    return parts


def parse_file(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> ProgramNest:
    text, _ = reader.read_text(path, syntax)
    name = os.path.splitext(os.path.basename(path))[0]
    return parse_text(text, name=name, path=path,
                      number=reader.program_number(path, syntax), syntax=syntax)


def find_report(nc_path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Optional[str]:
    """Найти отчёт наладки рядом с программой."""
    return reader.find_sibling(nc_path, syntax.fms_suffixes)


def find_document(nc_path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Optional[str]:
    """Найти карту наладки (PDF) рядом с программой.

    В реальном задании она есть не у всех программ, поэтому отсутствие —
    обычное дело, а не ошибка.
    """
    return reader.find_sibling(nc_path, syntax.document_suffixes)
