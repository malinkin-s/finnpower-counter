# -*- coding: utf-8 -*-
"""Отбор, строки таблицы и выгрузка — общее для консоли и окна."""

import csv
import io

import pytest

from finnpower_counter import presentation
from finnpower_counter.core import balance
from finnpower_counter.core.model import PartStatus


def status(part, total, last, produced):
    return PartStatus(part=part, total=total, last_program=last, produced=produced)


SAMPLE = [
    status('PART_NO01', 6, 7, 6),
    status('PART_NO02', 14, 12, 12),
    status('PART_NO13', 3, 1, 3),
]


def test_строка_таблицы():
    assert presentation.row(SAMPLE[0]) == ['PART_NO01', '6', '7', '6 / 6', 'Готово']
    assert presentation.row(SAMPLE[1]) == ['PART_NO02', '14', '12', '12 / 14', 'В работе']


def test_число_колонок_совпадает_с_числом_полей():
    assert all(len(r) == len(presentation.COLUMNS) for r in presentation.rows(SAMPLE))


def test_отбор_всех():
    assert presentation.filter_statuses(SAMPLE, presentation.ONLY_ALL) == SAMPLE


def test_отбор_готовых():
    got = presentation.filter_statuses(SAMPLE, presentation.ONLY_DONE)
    assert [s.part for s in got] == ['PART_NO01', 'PART_NO13']


def test_отбор_в_работе():
    got = presentation.filter_statuses(SAMPLE, presentation.ONLY_WORK)
    assert [s.part for s in got] == ['PART_NO02']


@pytest.mark.parametrize('needle', ['no13', 'NO13', ' no13 '])
def test_поиск_не_зависит_от_регистра_и_пробелов(needle):
    got = presentation.filter_statuses(SAMPLE, search=needle)
    assert [s.part for s in got] == ['PART_NO13']


def test_пустой_поиск_ничего_не_отсекает():
    assert presentation.filter_statuses(SAMPLE, search='   ') == SAMPLE
    assert presentation.filter_statuses(SAMPLE, search=None) == SAMPLE


def test_отбор_и_поиск_вместе():
    got = presentation.filter_statuses(SAMPLE, presentation.ONLY_DONE, 'no0')
    assert [s.part for s in got] == ['PART_NO01']


def test_итоги_считаются_по_всей_смене(shift_ok):
    """Отбор меняет показ, но не баланс."""
    statuses = balance.status_at(shift_ok, 9)
    line = presentation.counters(shift_ok, statuses)
    assert 'Готово полностью: 7 из 14' in line
    assert 'Деталей: 95' in line


def test_строка_сверки_чисто(shift_ok):
    result = balance.cross_check(shift_ok.programs)
    assert 'расхождений нет' in presentation.cross_check_line(result)


def test_строка_сверки_без_отчётов():
    class Empty(object):
        checked = 0
        skipped = 3
        mismatches = []
    assert 'не найдены' in presentation.cross_check_line(Empty())


def test_строка_сверки_с_расхождениями():
    class Broken(object):
        checked = 2
        skipped = 0
        mismatches = ['PRG_01: ...', 'PRG_02: ...']
    assert 'расхождений 2' in presentation.cross_check_line(Broken())


def test_сверка_не_выполнялась():
    assert presentation.cross_check_line(None) == 'Сверка не выполнялась'


def test_csv_разбирается_обратно():
    text = presentation.to_csv(SAMPLE, done_program=9)
    rows = list(csv.reader(io.StringIO(text), delimiter=';'))
    assert rows[0] == ['Выполнено программ:', '9']
    assert rows[1] == list(presentation.COLUMNS)
    assert len(rows) == 2 + len(SAMPLE)
    assert rows[2][0] == 'PART_NO01'


def test_csv_без_номера_программы():
    rows = list(csv.reader(io.StringIO(presentation.to_csv(SAMPLE)), delimiter=';'))
    assert rows[0] == list(presentation.COLUMNS)


def test_csv_пишется_с_bom(tmp_path):
    """Без BOM русский Excel открывает файл кракозябрами."""
    path = str(tmp_path / 'готовность.csv')
    presentation.write_csv(path, SAMPLE, done_program=9)
    with open(path, 'rb') as fh:
        raw = fh.read()
    assert raw.startswith(b'\xef\xbb\xbf')
    assert 'Готово'.encode('utf-8') in raw


def test_csv_переживает_полный_свод(shift_ok):
    statuses = balance.status_at(shift_ok, 12)
    rows = list(csv.reader(io.StringIO(presentation.to_csv(statuses)), delimiter=';'))
    assert len(rows) == 1 + shift_ok.unique_parts
