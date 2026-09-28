# -*- coding: utf-8 -*-
"""Порядок выполнения программ и разбор того, что ввёл оператор.

Набор `realistic` воспроизводит имена вида ДДММГГ + код + номер. На таких
именах число, выдернутое из имени, не возрастает и не уникально, поэтому
порядок выполнения по нему определяется неверно. Набор `unpadded` ловит
обратную ловушку: по алфавиту PRG_10 встаёт перед PRG_9.
"""

import os

import pytest

from finnpower_counter.core import balance, reader


@pytest.fixture(scope='module')
def realistic(request):
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
    return balance.load_shift(os.path.join(root, 'realistic'))


# --- естественная сортировка ---

@pytest.mark.parametrize('names', [
    ['PRG_01', 'PRG_02', 'PRG_10', 'PRG_30'],
    ['PRG_1', 'PRG_2', 'PRG_9', 'PRG_10', 'PRG_12'],
    ['000101zz201001', '000101zz202004', '000102zz201001', '000103zz202001'],
])
def test_естественная_сортировка_сохраняет_порядок(names):
    assert sorted(names, key=reader.natural_key) == names


def test_алфавитная_сортировка_ломается_без_ведущих_нулей():
    names = ['PRG_1', 'PRG_2', 'PRG_9', 'PRG_10']
    assert sorted(names) != names
    assert sorted(names, key=reader.natural_key) == names


def test_ключ_не_зависит_от_расширения_и_папки():
    assert reader.natural_key('/цех/PRG_07.nc') == reader.natural_key('PRG_07.NC')


# --- набор с именами реального вида ---

def test_числа_из_имён_не_годятся_для_порядка(realistic):
    """Ровно та ошибка, ради которой заведён этот набор."""
    numbers = [n.number for n in realistic.programs]
    assert numbers != sorted(numbers), 'набор должен ломать сортировку по числу'
    assert len(set(numbers)) < len(numbers), 'набор должен содержать дубликаты'


def test_места_идут_подряд(realistic):
    places = [n.position for n in realistic.programs]
    assert places == list(range(1, len(places) + 1))


def test_порядок_совпадает_с_замыслом(realistic, expected):
    want = [expected['realistic_names'][str(i)]
            for i in range(1, len(realistic.programs) + 1)]
    assert [n.name for n in realistic.programs] == want


def test_свод_такой_же_как_на_обычных_именах(realistic, expected):
    """Имена другие, задание то же — цифры обязаны совпасть."""
    assert realistic.unique_parts == expected['unique_parts']
    assert realistic.total_pieces == expected['total_pieces']
    got = [{'part': p.part, 'total': p.total, 'last_position': p.last_position}
           for p in realistic.parts]
    want = [{k: v for k, v in p.items() if k != 'last_program'}
            for p in expected['parts']]
    assert got == want


def test_крайняя_программа_показывается_именем(realistic, expected):
    for part in realistic.parts:
        assert part.last_program == expected['realistic_names'][str(part.last_position)]


def test_сверка_с_отчётами_проходит(realistic):
    assert balance.cross_check(realistic.programs).is_clean


@pytest.mark.parametrize('done, complete', [
    (None, 0), (1, 1), (2, 2), (7, 3), (9, 7), (11, 11), (12, 14),
])
def test_готовность_по_ходу_смены_не_зависит_от_имён(realistic, done, complete):
    statuses = balance.status_for(realistic, balance.positions_upto(realistic, done))
    assert sum(1 for s in statuses if s.is_complete) == complete


# --- разбор ввода оператора ---

def test_пустой_ввод_это_смена_не_начата(shift_ok):
    assert balance.resolve_position(shift_ok, '') is None
    assert balance.resolve_position(shift_ok, '   ') is None
    assert balance.resolve_position(shift_ok, None) is None


@pytest.mark.parametrize('text, place', [('1', 1), ('7', 7), ('12', 12)])
def test_место_в_задании(shift_ok, text, place):
    assert balance.resolve_position(shift_ok, text) == place


def test_имя_программы_целиком(shift_ok):
    assert balance.resolve_position(shift_ok, 'PRG_07') == 7
    assert balance.resolve_position(shift_ok, 'prg_07') == 7


def test_имя_программы_на_реальных_именах(realistic, expected):
    name = expected['realistic_names']['9']
    assert balance.resolve_position(realistic, name) == 9


def test_отличимый_кусок_имени(realistic):
    """У 000102zz203001 хвост 203001 больше ни у кого не встречается."""
    assert balance.resolve_position(realistic, '203001') == 9


def test_неотличимый_кусок_имени_отвергается(realistic):
    """Хвост 201001 есть у трёх программ разных дат — угадывать нельзя."""
    with pytest.raises(ValueError) as info:
        balance.resolve_position(realistic, '201001')
    assert info.value.args[0].key == 'done.ambiguous'


def test_неизвестный_ввод_отвергается(shift_ok):
    with pytest.raises(ValueError) as info:
        balance.resolve_position(shift_ok, 'такого нет')
    assert info.value.args[0].key == 'done.unknown'


def test_число_за_концом_задания_это_вся_смена(shift_ok):
    assert balance.resolve_position(shift_ok, '999') == 12


def test_место_важнее_имени(realistic):
    """Цифры сначала пробуются как место: так привычнее оператору."""
    assert balance.resolve_position(realistic, '1') == 1
