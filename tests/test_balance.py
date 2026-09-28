# -*- coding: utf-8 -*-
"""Свод смены против эталона."""

import os

import pytest

from finnpower_counter.core import balance


def test_итог_совпадает_с_эталоном(shift_ok, expected):
    assert shift_ok.unique_parts == expected['unique_parts']
    assert shift_ok.total_pieces == expected['total_pieces']
    assert len(shift_ok.usable_programs) == expected['programs']


def test_каждая_позиция_совпадает_с_эталоном(shift_ok, expected):
    got = [{'part': p.part, 'total': p.total,
            'last_position': p.last_position, 'last_program': p.last_program}
           for p in shift_ok.parts]
    assert got == expected['parts']


def test_разбивка_по_программам_совпадает_с_эталоном(shift_ok, expected):
    for part in shift_ok.parts:
        for number, count in part.by_program.items():
            assert expected['per_program'][str(number)][part.part] == count


def test_исправная_смена_без_предупреждений(shift_ok):
    assert shift_ok.warnings == []


def test_сверка_с_отчётами_наладки_чистая(shift_ok):
    """Сходятся три независимых источника: .nc, #RSCUT и #COMPONENTS."""
    result = balance.cross_check(shift_ok.programs)
    assert result.checked == len(shift_ok.programs)
    assert result.mismatches == []
    assert result.is_clean


@pytest.mark.parametrize('done, complete', [
    (None, 0), (1, 1), (2, 2), (7, 3), (9, 7), (11, 11), (12, 14),
])
def test_готовность_по_ходу_смены(shift_ok, done, complete):
    statuses = balance.status_for(shift_ok, balance.positions_upto(shift_ok, done))
    assert sum(1 for s in statuses if s.is_complete) == complete


def test_изготовлено_не_превышает_тираж(shift_ok, expected):
    for done in range(0, expected['programs'] + 2):
        for status in balance.status_for(shift_ok, balance.positions_upto(shift_ok, done)):
            assert 0 <= status.produced <= status.total
            assert status.remaining >= 0


def test_к_концу_смены_изготовлено_всё(shift_ok, expected):
    statuses = balance.status_for(shift_ok, balance.positions_upto(shift_ok, expected['programs']))
    assert all(s.is_complete for s in statuses)
    assert sum(s.produced for s in statuses) == expected['total_pieces']


def test_позиция_закрыта_ровно_на_своей_крайней_программе(shift_ok):
    for part in shift_ok.parts:
        before = balance.status_for(shift_ok, balance.positions_upto(shift_ok, part.last_position - 1))
        after = balance.status_for(shift_ok, balance.positions_upto(shift_ok, part.last_position))
        assert not [s for s in before if s.part == part.part][0].is_complete
        assert [s for s in after if s.part == part.part][0].is_complete


def test_папки_не_существует(tmp_path):
    with pytest.raises(NotADirectoryError):
        balance.load_shift(str(tmp_path / 'нет-такой-папки'))


def test_пустая_папка(tmp_path):
    summary = balance.load_shift(str(tmp_path))
    assert summary.parts == []
    assert summary.warnings


# --- нечитаемые файлы ---

@pytest.fixture
def shift_copy(tmp_path, fixtures_dir):
    import shutil
    target = tmp_path / 'shift'
    shutil.copytree(os.path.join(fixtures_dir, 'shift_ok'), str(target))
    return str(target)


def _deny(monkeypatch, suffix, stem='PRG_05'):
    """Отказ в доступе к одному файлу, как у заблокированного на Windows."""
    from finnpower_counter.core import reader
    original = reader.read_text

    def read_text(path, syntax=None):
        if os.path.basename(path) == stem + suffix:
            raise PermissionError(13, 'Permission denied', path)
        return original(path) if syntax is None else original(path, syntax)

    monkeypatch.setattr(reader, 'read_text', read_text)


def test_нечитаемая_программа_не_мешает_открыть_смену(shift_copy, monkeypatch):
    _deny(monkeypatch, '.nc')
    summary = balance.load_shift(shift_copy)
    broken = next(n for n in summary.programs if n.name == 'PRG_05')
    assert not broken.is_usable
    assert broken.position == 5, 'место в задании сохраняется'
    assert any(w.key == 'warn.unreadable' for w in summary.warnings)
    assert summary.parts


def test_нечитаемая_программа_не_даёт_расхождений(shift_copy, monkeypatch):
    _deny(monkeypatch, '.nc')
    summary = balance.load_shift(shift_copy)
    result = balance.cross_check(summary.programs)
    assert result.mismatches == []
    assert result.skipped == 1


def test_нечитаемый_отчёт_наладки_пропускается(shift_copy, monkeypatch):
    summary = balance.load_shift(shift_copy)
    _deny(monkeypatch, '.fms')
    result = balance.cross_check(summary.programs)
    assert result.skipped == 1
    assert result.checked == len(summary.programs) - 1
    assert result.mismatches == []


# --- ввод номера ---

def test_надстрочная_цифра_не_роняет_разбор_ввода(shift_ok):
    """«²» — isdigit, но не число для int()."""
    with pytest.raises(ValueError) as caught:
        balance.resolve_position(shift_ok, '²')
    assert hasattr(caught.value.args[0], 'key')
