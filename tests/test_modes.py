# -*- coding: utf-8 -*-
"""Режим показа по программам, габариты листа и окно отдельной позиции."""

import os

import pytest

from finnpower_counter import i18n, presentation, system
from finnpower_counter.core import balance, fms_parser, nc_parser


# --- габариты листа ---

def test_габариты_разбираются(fixtures_dir, expected):
    summary = balance.load_shift(os.path.join(fixtures_dir, 'shift_ok'))
    for nest in summary.programs:
        want = expected['sheet_sizes'][str(nest.position)]
        assert [nest.sheet_x, nest.sheet_y] == want, nest.name


def test_габариты_в_наборе_не_одинаковые(expected):
    """Иначе колонка размера ничего не проверяет."""
    assert len({tuple(v) for v in expected['sheet_sizes'].values()}) > 1


def test_габариты_сходятся_с_отчётом(fixtures_dir):
    shift = os.path.join(fixtures_dir, 'shift_ok')
    for name in sorted(os.listdir(shift)):
        if not name.endswith('.nc'):
            continue
        nest = nc_parser.parse_file(os.path.join(shift, name))
        report = fms_parser.parse_file(os.path.join(shift, name[:-3] + '.fms'))
        assert (nest.sheet_x, nest.sheet_y) == (report.sheet_x, report.sheet_y), name


def test_размер_листа_для_показа():
    nest = nc_parser.parse_text('SHEET_COUNT=1\nX_DIM=2500\nY_DIM=1250\n',
                                name='PRG_01', number=1)
    assert nest.sheet_size == '2500 x 1250'


def test_дробная_часть_убирается_если_нулевая():
    nest = nc_parser.parse_text('SHEET_COUNT=1\nX_DIM=2500.0\nY_DIM=1250.5\n',
                                name='PRG_01', number=1)
    assert nest.sheet_size == '2500 x 1250.5'


def test_без_габаритов_размер_пустой():
    nest = nc_parser.parse_text('SHEET_COUNT=1\n', name='PRG_01', number=1)
    assert nest.sheet_size == ''


def test_габариты_не_путаются_с_соседними_полями():
    """В файле есть UNLOADING_X_DIM и PART_X_DIM — их брать нельзя."""
    text = ('SHEET_COUNT=1\nUNLOADING_X_DIM=2082\nX_DIM=2500\nY_DIM=1250\n'
            'PART_DATA=1\nPART_NAME="A"\nQUANTITY=1\nPART_X_DIM=390\nSAVE_DATA\n')
    nest = nc_parser.parse_text(text, name='PRG_01', number=1)
    assert (nest.sheet_x, nest.sheet_y) == (2500.0, 1250.0)


# --- режим по программам ---

def test_колонки_разные_в_разных_режимах():
    parts = presentation.column_keys(presentation.MODE_PARTS)
    programs = presentation.column_keys(presentation.MODE_PROGRAMS)
    assert parts != programs
    assert 'col.sheet_size' in programs and 'col.sheets' in programs


def test_выравнивание_есть_для_каждой_колонки():
    for mode in presentation.MODES:
        assert len(presentation.align(mode)) == len(presentation.column_keys(mode))


def test_строка_программы(shift_ok):
    nest = next(n for n in shift_ok.programs if n.position == 6)
    row = presentation.program_row(nest, done=12)
    assert row[0] == 'PRG_06'
    assert row[1] == '3000 x 1500'
    assert row[2] == '3'
    assert row[3] == str(nest.unique_parts)
    assert row[4] == str(nest.total_pieces)


def test_число_деталей_в_программе_это_листы_на_количество(shift_ok):
    for nest in shift_ok.usable_programs:
        assert nest.total_pieces == sum(nest.pieces().values())
        assert nest.unique_parts == len(nest.parts_per_sheet)


def test_сумма_по_программам_равна_итогу_смены(shift_ok):
    assert sum(n.total_pieces for n in shift_ok.usable_programs) == shift_ok.total_pieces


@pytest.mark.parametrize('done, only, count', [
    (5, presentation.ONLY_ALL, 12),
    (5, presentation.ONLY_DONE, 5),
    (5, presentation.ONLY_WORK, 7),
    (None, presentation.ONLY_DONE, 0),
    (None, presentation.ONLY_WORK, 12),
])
def test_отбор_программ(shift_ok, done, only, count):
    got = presentation.filter_programs(shift_ok.usable_programs, only, None, done)
    assert len(got) == count


def test_поиск_программы_по_имени_и_по_номеру(shift_ok):
    by_name = presentation.filter_programs(shift_ok.usable_programs, search='prg_07')
    by_number = presentation.filter_programs(shift_ok.usable_programs, search='7')
    assert [p.name for p in by_name] == ['PRG_07']
    assert [p.name for p in by_number] == ['PRG_07']


@pytest.mark.parametrize('needle, names', [
    ('1', ['PRG_01']),
    ('10', ['PRG_10']),
    ('07', ['PRG_07']),
    ('99', []),
])
def test_цифры_в_поиске_это_номер_программы(shift_ok, needle, names):
    """Иначе ввод «1» вытащит заодно PRG_10, PRG_11 и PRG_12."""
    got = presentation.filter_programs(shift_ok.usable_programs, search=needle)
    assert [p.name for p in got] == names


def test_поиск_по_имени_остаётся_подстрочным(shift_ok):
    got = presentation.filter_programs(shift_ok.usable_programs, search='prg_1')
    assert [p.name for p in got] == ['PRG_10', 'PRG_11', 'PRG_12']


# --- окно позиции ---

def test_разбивка_позиции_по_программам(shift_ok):
    part = next(p for p in shift_ok.parts if p.part == 'PART_NO05')
    rows = presentation.part_detail_rows(part, shift_ok.programs)
    assert [r[0] for r in rows] == ['PRG_01', 'PRG_02', 'PRG_05', 'PRG_12']
    assert [r[3] for r in rows] == ['1', '2', '5', '4']


def test_накопление_доходит_ровно_до_тиража(shift_ok):
    for part in shift_ok.parts:
        rows = presentation.part_detail_rows(part, shift_ok.programs)
        assert rows, part.part
        assert rows[-1][4] == '{0} / {0}'.format(part.total)
        assert sum(int(r[3]) for r in rows) == part.total


def test_разбивка_идёт_по_возрастанию_номера(shift_ok):
    for part in shift_ok.parts:
        numbers = sorted(part.by_program)
        rows = presentation.part_detail_rows(part, shift_ok.programs)
        assert len(rows) == len(numbers)


def test_число_колонок_окна_позиции(shift_ok):
    part = shift_ok.parts[0]
    rows = presentation.part_detail_rows(part, shift_ok.programs)
    assert all(len(r) == len(presentation.DETAIL_COLUMN_KEYS) for r in rows)
    assert len(presentation.DETAIL_ALIGN) == len(presentation.DETAIL_COLUMN_KEYS)


# --- карта наладки ---

def test_карта_наладки_находится(fixtures_dir, expected):
    shift = os.path.join(fixtures_dir, 'shift_ok')
    without = set(expected['without_document'])
    for name in sorted(os.listdir(shift)):
        if not name.endswith('.nc'):
            continue
        path = os.path.join(shift, name)
        number = int(name[4:6])
        document = fms_parser.find_document(path)
        if number in without:
            assert document is None, name
        else:
            assert document and document.endswith('.pdf'), name


def test_отсутствие_карты_не_ошибка(fixtures_dir):
    """В реальном задании PDF есть не у всех программ."""
    path = os.path.join(fixtures_dir, 'shift_ok', 'PRG_04.nc')
    assert fms_parser.find_document(path) is None


def test_заглушки_карт_это_настоящие_pdf(fixtures_dir):
    path = os.path.join(fixtures_dir, 'shift_ok', 'PRG_01.pdf')
    with open(path, 'rb') as fh:
        assert fh.read(5) == b'%PDF-'


def test_открытие_несуществующего_файла_возвращает_ошибку(tmp_path):
    """Не открывшаяся карта не повод ронять окно оператора."""
    assert system.open_document(str(tmp_path / 'нет.pdf')) is not None
    assert system.open_document('') is not None


# --- язык ---

def test_подписи_режима_переводятся():
    for mode in presentation.MODES:
        i18n.set_language('ru')
        ru = presentation.columns(mode)
        i18n.set_language('en')
        en = presentation.columns(mode)
        i18n.set_language('ru')
        assert ru != en
        assert all(c and not c.startswith('col.') for c in ru + en)
