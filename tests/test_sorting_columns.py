# -*- coding: utf-8 -*-
"""Сортировка по колонкам и отметки выполненных программ."""

import pytest

from finnpower_counter import presentation
from finnpower_counter.core import balance


# --- сортировка позиций ---

def test_по_умолчанию_по_артикулу(shift_ok):
    statuses = balance.status_at(shift_ok, 9)
    got = presentation.sort_statuses(statuses)
    assert [s.part for s in got] == sorted(s.part for s in statuses)


@pytest.mark.parametrize('column, attr', [
    ('col.total', 'total'),
    ('col.produced', 'produced'),
    ('col.last_program', 'last_position'),
])
def test_числовые_колонки_сортируются_как_числа(shift_ok, column, attr):
    statuses = balance.status_at(shift_ok, 9)
    values = [getattr(s, attr) for s in presentation.sort_statuses(statuses, column)]
    assert values == sorted(values)


def test_обратный_порядок(shift_ok):
    statuses = balance.status_at(shift_ok, 9)
    values = [s.total for s in presentation.sort_statuses(statuses, 'col.total', True)]
    assert values == sorted(values, reverse=True)


def test_крайняя_упорядочивается_по_месту_а_не_по_имени(shift_ok):
    """В ячейке имя программы, а порядок должен быть по месту в задании."""
    statuses = balance.status_at(shift_ok, 12)
    got = presentation.sort_statuses(statuses, 'col.last_program')
    assert [s.last_position for s in got] == sorted(s.last_position for s in statuses)


def test_равные_значения_упорядочены_устойчиво(shift_ok):
    """Иначе строки с одинаковым тиражом прыгают при каждой перерисовке."""
    statuses = balance.status_at(shift_ok, 9)
    first = presentation.sort_statuses(statuses, 'col.status')
    second = presentation.sort_statuses(list(reversed(statuses)), 'col.status')
    assert [s.part for s in first] == [s.part for s in second]


def test_сортировка_не_теряет_и_не_плодит_строки(shift_ok):
    statuses = balance.status_at(shift_ok, 9)
    for column in list(presentation.PART_SORT_KEYS) + [None]:
        got = presentation.sort_statuses(statuses, column)
        assert sorted(s.part for s in got) == sorted(s.part for s in statuses)


# --- сортировка программ ---

def test_программы_по_умолчанию_по_месту(shift_ok):
    got = presentation.sort_programs(shift_ok.usable_programs)
    assert [n.position for n in got] == sorted(n.position for n in got)


@pytest.mark.parametrize('column, attr', [
    ('col.sheets', 'sheet_count'),
    ('col.positions', 'unique_parts'),
    ('col.pieces', 'total_pieces'),
])
def test_числовые_колонки_программ(shift_ok, column, attr):
    got = presentation.sort_programs(shift_ok.usable_programs, column)
    values = [getattr(n, attr) for n in got]
    assert values == sorted(values)


def test_размер_листа_сортируется_по_площади(shift_ok):
    got = presentation.sort_programs(shift_ok.usable_programs, 'col.sheet_size')
    areas = [(n.sheet_x or 0) * (n.sheet_y or 0) for n in got]
    assert areas == sorted(areas)
    assert areas[0] < areas[-1], 'в наборе должны быть разные листы'


def test_сортировка_по_отметке(shift_ok):
    done = {2, 5, 7}
    got = presentation.sort_programs(shift_ok.usable_programs, 'col.mark',
                                     reverse=True, done=done)
    assert {n.position for n in got[:3]} == done


def test_неизвестная_колонка_даёт_порядок_по_умолчанию(shift_ok):
    got = presentation.sort_programs(shift_ok.usable_programs, 'col.нетакой')
    assert [n.position for n in got] == sorted(n.position for n in got)


# --- что можно сортировать ---

def test_сортируются_все_колонки_режима():
    for mode in presentation.MODES:
        for column in presentation.column_keys(mode):
            assert presentation.sortable(mode, column), column


def test_колонки_программ_не_сортируются_в_режиме_деталей():
    assert not presentation.sortable(presentation.MODE_PARTS, 'col.sheets')


def test_короткие_имена_колонок_для_консоли():
    assert presentation.sort_column(presentation.MODE_PARTS, 'total') == 'col.total'
    assert presentation.sort_column(presentation.MODE_PROGRAMS, 'pieces') == 'col.pieces'
    assert presentation.sort_column(presentation.MODE_PARTS, 'pieces') is None
    assert presentation.sort_column(presentation.MODE_PARTS, None) is None


def test_заголовок_показывает_направление():
    plain = presentation.heading('col.total', None, False)
    up = presentation.heading('col.total', 'col.total', False)
    down = presentation.heading('col.total', 'col.total', True)
    assert up.startswith(plain) and down.startswith(plain)
    assert up != plain and down != plain and up != down


# --- отметки выполнения ---

def test_ввод_номера_отмечает_всё_подряд(shift_ok):
    assert balance.positions_upto(shift_ok, 5) == {1, 2, 3, 4, 5}
    assert balance.positions_upto(shift_ok, None) == set()


def test_произвольный_набор_считается_верно(shift_ok):
    """Программы не всегда идут подряд — пропуск должен учитываться."""
    full = balance.status_for(shift_ok, {1, 2, 3, 4, 5})
    gap = balance.status_for(shift_ok, {1, 2, 4, 5})
    produced_full = {s.part: s.produced for s in full}
    produced_gap = {s.part: s.produced for s in gap}
    assert produced_gap != produced_full
    assert all(produced_gap[p] <= produced_full[p] for p in produced_full)


def test_набор_и_номер_дают_одно_и_то_же(shift_ok):
    by_number = balance.status_at(shift_ok, 7)
    by_set = balance.status_for(shift_ok, balance.positions_upto(shift_ok, 7))
    assert by_number == by_set


def test_пустой_набор_это_ноль(shift_ok):
    assert all(s.produced == 0 for s in balance.status_for(shift_ok, set()))


def test_полный_набор_закрывает_всё(shift_ok):
    statuses = balance.status_for(shift_ok, set(shift_ok.positions))
    assert all(s.is_complete for s in statuses)


def test_отбор_готовых_идёт_по_отметкам(shift_ok):
    done = {3, 8}
    got = presentation.filter_programs(shift_ok.usable_programs,
                                       presentation.ONLY_DONE, None, done)
    assert {n.position for n in got} == done
