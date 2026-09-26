# -*- coding: utf-8 -*-
"""Проверка на реальном сменном задании.

Цеховые файлы в репозиторий не выкладываются, поэтому тест пропускается,
если папки нет. Локально он ценен тем, что сверяет разбор 30 программ с их
отчётами наладки — с данными, которые утилита не порождала.

Путь можно задать переменной окружения FINNPOWER_DATASET.
"""

import os

import pytest

from finnpower_counter.core import balance

DATASET = os.environ.get(
    'FINNPOWER_DATASET',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'cnc_finnpower'))

pytestmark = pytest.mark.skipif(
    not os.path.isdir(DATASET),
    reason='нет папки с реальным датасетом: {}'.format(DATASET))


@pytest.fixture(scope='module')
def shift():
    return balance.load_shift(DATASET)


def test_смена_читается_целиком(shift):
    assert len(shift.usable_programs) == len(shift.programs)
    assert shift.programs


def test_разбор_сходится_с_отчётами_наладки(shift):
    result = balance.cross_check(shift.programs)
    assert result.checked == len(shift.programs)
    assert result.mismatches == []


def test_нет_предупреждений(shift):
    assert shift.warnings == []


def test_баланс_сходится(shift):
    """Сумма по позициям равна сумме тиражей по программам."""
    by_program = sum(p.total_pieces for p in shift.usable_programs)
    assert shift.total_pieces == by_program


def test_крайняя_программа_не_дальше_конца_задания(shift):
    last = max(p.position for p in shift.usable_programs)
    names = {p.name for p in shift.usable_programs}
    for part in shift.parts:
        assert part.last_position <= last
        assert part.last_program in names
        assert part.total == sum(part.by_program.values())


def test_места_идут_подряд_без_пропусков(shift):
    places = [p.position for p in shift.programs]
    assert places == list(range(1, len(places) + 1))
