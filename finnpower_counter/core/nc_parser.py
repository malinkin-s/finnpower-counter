# -*- coding: utf-8 -*-
"""Разбор управляющей программы (.nc)."""

import os
from typing import List, Optional

from . import reader
from .model import Note, ProgramNest
from .syntax import DEFAULT_SYNTAX, MachineSyntax


def parse_text(text: str,
               name: str,
               path: str = '',
               number: Optional[int] = None,
               syntax: MachineSyntax = DEFAULT_SYNTAX) -> ProgramNest:
    """Разобрать текст программы."""
    text = reader.normalize_newlines(text)
    warnings: List[Note] = []

    match = syntax.sheet_count.search(text)
    if match is None:
        sheet_count = None
        warnings.append(Note('warn.no_sheet_count'))
    else:
        sheet_count = int(match.group(1))
        if sheet_count == 0:
            warnings.append(Note('warn.zero_sheets'))

    parts = {}
    blocks = syntax.part_block.findall(text)
    for index, block in enumerate(blocks, start=1):
        name_match = syntax.part_name.search(block)
        qty_match = syntax.quantity.search(block)
        if name_match is None or qty_match is None:
            warnings.append(Note('warn.block_skipped', {
                'index': index,
                'field': 'PART_NAME' if name_match is None else 'QUANTITY'}))
            continue
        part = name_match.group(1).strip()
        if not part or syntax.is_scrap(part):
            continue
        # Одна деталь может лежать в нескольких блоках одного файла —
        # количества складываются, а не перезаписываются.
        parts[part] = parts.get(part, 0) + int(qty_match.group(1))

    if blocks and not parts and not warnings:
        warnings.append(Note('warn.only_scrap'))

    return ProgramNest(
        number=number if number is not None else -1,
        name=name,
        path=path,
        sheet_count=sheet_count,
        parts_per_sheet=parts,
        warnings=warnings,
    )


def parse_file(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> ProgramNest:
    """Разобрать файл программы."""
    text, encoding = reader.read_text(path, syntax)
    name = os.path.splitext(os.path.basename(path))[0]
    number = reader.program_number(path, syntax)

    nest = parse_text(text, name=name, path=path, number=number, syntax=syntax)
    if number is None:
        nest.warnings.append(Note('warn.no_number'))
    if encoding not in ('utf-8', 'utf-8-sig'):
        nest.warnings.append(Note('warn.encoding', {'encoding': encoding}))
    return nest


def collect_programs(directory: str,
                     syntax: MachineSyntax = DEFAULT_SYNTAX) -> List[ProgramNest]:
    """Разобрать все программы в папке, по возрастанию номера."""
    nests = []
    for entry in sorted(os.listdir(directory)):
        path = os.path.join(directory, entry)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(entry)[1].lower() not in syntax.nc_suffixes:
            continue
        nests.append(parse_file(path, syntax))
    nests.sort(key=lambda n: (n.number, n.name))
    return nests
