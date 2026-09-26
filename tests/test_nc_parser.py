# -*- coding: utf-8 -*-
"""Разбор управляющей программы, включая особенности формата."""

import os

import pytest

from finnpower_counter.core import nc_parser

HEADER = 'SHEET_COUNT={sheets}\n'
BLOCK = (
    'PART_DATA={index}\n'
    'PART_NAME="{name}"\n'
    'PART_ID=1\n'
    'QUANTITY={qty}\n'
    'ANGLE=0\n'
    'SAVE_DATA\n'
)
TAIL = 'IF (SHEET_COUNT > R400) AND ($A_IN[16]==1) GOTOB MAIN\nM30\n'


def build(sheets, blocks, tail=TAIL):
    text = HEADER.format(sheets=sheets)
    for index, (name, qty) in enumerate(blocks, start=1):
        text += BLOCK.format(index=index, name=name, qty=qty)
    return text + tail


def test_тираж_это_листы_на_количество():
    nest = nc_parser.parse_text(build(3, [('A', 4)]), name='PRG_01', number=1)
    assert nest.sheet_count == 3
    assert nest.parts_per_sheet == {'A': 4}
    assert nest.pieces() == {'A': 12}


def test_повторные_блоки_одной_детали_складываются():
    """Одна деталь часто разнесена по листу несколькими блоками PART_DATA."""
    nest = nc_parser.parse_text(
        build(2, [('A', 3), ('B', 1), ('A', 1), ('A', 1)]), name='PRG_01', number=1)
    assert nest.parts_per_sheet == {'A': 5, 'B': 1}
    assert nest.pieces() == {'A': 10, 'B': 2}


def test_второе_вхождение_sheet_count_не_объявление():
    """В конце программы SHEET_COUNT стоит в условии перехода."""
    text = build(2, [('A', 1)])
    assert text.count('SHEET_COUNT') == 2
    assert nc_parser.parse_text(text, name='PRG_01', number=1).sheet_count == 2


def test_обрезки_в_учёт_не_идут():
    nest = nc_parser.parse_text(
        build(1, [('SCRAP', 1), ('A', 2), ('SCRAP', 1)]), name='PRG_01', number=1)
    assert nest.parts_per_sheet == {'A': 2}


def test_обрезки_в_любом_регистре():
    nest = nc_parser.parse_text(build(1, [('scrap', 1), ('A', 1)]),
                               name='PRG_01', number=1)
    assert nest.parts_per_sheet == {'A': 1}


def test_блок_без_количества_пропускается_с_предупреждением():
    text = build(1, [('A', 1), ('B', 2)]).replace('QUANTITY=1\n', '')
    nest = nc_parser.parse_text(text, name='PRG_01', number=1)
    assert nest.parts_per_sheet == {'B': 2}
    assert any('QUANTITY' in str(w) for w in nest.warnings)


def test_без_sheet_count_программа_непригодна():
    """Подставлять единицу нельзя: расчёт уйдёт в ошибку молча."""
    nest = nc_parser.parse_text(build(1, [('A', 1)]).replace('SHEET_COUNT=1\n', ''),
                               name='PRG_01', number=1)
    assert nest.sheet_count is None
    assert not nest.is_usable
    assert nest.pieces() == {}
    assert nest.warnings


def test_sheet_count_ноль_даёт_ноль_деталей():
    nest = nc_parser.parse_text(build(0, [('A', 5)]), name='PRG_01', number=1)
    assert nest.is_usable
    assert nest.pieces() == {'A': 0}
    assert nest.warnings


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_разбор_не_зависит_от_переводов_строк(newline):
    text = build(2, [('A', 3)]).replace('\n', newline)
    nest = nc_parser.parse_text(text, name='PRG_01', number=1)
    assert nest.sheet_count == 2
    assert nest.pieces() == {'A': 6}


def test_пустой_файл():
    nest = nc_parser.parse_text('', name='PRG_01', number=1)
    assert not nest.is_usable
    assert nest.parts_per_sheet == {}


def test_только_обрезки():
    nest = nc_parser.parse_text(build(1, [('SCRAP', 1)]), name='PRG_01', number=1)
    assert nest.parts_per_sheet == {}
    assert any(w.key == 'warn.only_scrap' for w in nest.warnings)


def test_незакрытый_блок_не_ломает_разбор():
    text = HEADER.format(sheets=1) + 'PART_DATA=1\nPART_NAME="A"\nQUANTITY=2\n' + TAIL
    nest = nc_parser.parse_text(text, name='PRG_01', number=1)
    assert nest.sheet_count == 1
    assert nest.parts_per_sheet == {}


def test_краевые_файлы_разбираются_без_исключений(edge_dir):
    for name in sorted(os.listdir(edge_dir)):
        if not name.endswith('.nc'):
            continue
        nest = nc_parser.parse_file(os.path.join(edge_dir, name))
        assert isinstance(nest.parts_per_sheet, dict)
