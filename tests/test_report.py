# -*- coding: utf-8 -*-
"""Отчёты об ошибках.

Главное требование: отчёт прикладывают к сообщению об ошибке в открытом
репозитории, поэтому заводских обозначений в нём быть не должно.
"""

import os

import pytest

from finnpower_counter import __version__, report
from finnpower_counter.core import balance


@pytest.fixture
def broken():
    try:
        raise ValueError('сбой на 000101zz201001 в C:\\CAM\\PROGRAMS\\240729\\деталь.nc')
    except ValueError:
        import sys
        return sys.exc_info()


# --- обезличивание ---

def test_имена_программ_и_деталей_заменяются(shift_ok):
    text = report.build(shift_ok)
    for nest in shift_ok.programs:
        assert nest.name not in text or nest.name.startswith('PRG_')
    assert 'PRG_01' in text


def test_ни_одно_обозначение_не_просачивается():
    """Подстановка строится из самого задания, а не из списка исключений."""
    scrubber = report.Scrubber(programs=['000101zz201001', '000102zz203001'],
                               parts=['555001_zz2', '555002000_zz2'])
    text = scrubber.text('деталь 555001_zz2 в 000101zz201001 и 555002000_zz2')
    for real in ('555001_zz2', '555002000_zz2', '000101zz201001'):
        assert real not in text
    assert 'PART_01' in text and 'PRG_01' in text


def test_длинные_обозначения_заменяются_первыми():
    """Иначе короткое имя съест часть длинного и оставит хвост."""
    scrubber = report.Scrubber(parts=['555001', '555001_zz2'])
    text = scrubber.text('555001_zz2')
    assert '555001' not in text


def test_подстановка_устойчива():
    """По отчёту должно быть видно, что это одна и та же программа."""
    scrubber = report.Scrubber(programs=['a1', 'b2'])
    assert scrubber.text('a1') == scrubber.text('a1')
    assert scrubber.text('a1') != scrubber.text('b2')


@pytest.mark.parametrize('path', [
    r'C:\CAM\PROGRAMS\240729\PRG_07.nc',
    '/home/оператор/цех/смена/PRG_07.nc',
    r'\\SERVER\SHARE\PRG_07.nc',
])
def test_пути_урезаются_до_имени_файла(path):
    text = report.scrub_paths('ошибка в {}'.format(path))
    assert 'PROGRAMS' not in text and 'оператор' not in text
    assert 'SERVER' not in text
    assert 'PRG_07.nc' in text


def test_домашний_каталог_не_попадает(shift_ok, broken):
    text = report.build(shift_ok, broken)
    assert os.path.expanduser('~') not in text


def test_никаких_абсолютных_путей(shift_ok, broken):
    import re
    text = report.build(shift_ok, broken)
    assert not re.search(r'[A-Za-z]:\\', text)
    assert '/home/' not in text


# --- содержимое ---

def test_версия_и_среда_указаны(shift_ok):
    text = report.build(shift_ok)
    assert __version__ in text
    assert 'Python' in text


def test_трассировка_попадает(shift_ok, broken):
    text = report.build(shift_ok, broken)
    assert 'Traceback' in text
    assert 'ValueError' in text


def test_скелет_задания_попадает(shift_ok):
    text = report.build(shift_ok)
    assert 'Программ' in text
    assert str(shift_ok.total_pieces) in text
    for nest in shift_ok.programs:
        assert 'листов={}'.format(nest.sheet_count) in text


def test_замечания_идут_ключами_а_не_текстом(fixtures_dir):
    """В тексте замечания может оказаться имя файла, в ключе — нет."""
    summary = balance.load_shift(os.path.join(fixtures_dir, 'edge'))
    text = report.build(summary)
    assert 'warn.' in text


def test_без_задания_отчёт_всё_равно_собирается():
    text = report.build(None)
    assert 'не была открыта' in text
    assert __version__ in text


def test_последние_действия_обезличиваются(shift_ok):
    text = report.build(shift_ok, actions=[r'открыта C:\CAM\PROGRAMS\240729'])
    assert 'PROGRAMS' not in text


# --- запись ---

def test_отчёт_записывается(tmp_path, shift_ok):
    path = report.save(shift_ok, directory=str(tmp_path))
    assert path and os.path.isfile(path)
    with open(path, encoding='utf-8-sig') as fh:
        assert __version__ in fh.read()


def test_имя_файла_с_отметкой_времени(tmp_path, shift_ok):
    path = report.save(shift_ok, directory=str(tmp_path))
    name = os.path.basename(path)
    assert name.startswith(report.FILE_PREFIX) and name.endswith('.txt')


def test_запись_в_недоступную_папку_не_роняет(shift_ok):
    """Не сумев сохранить отчёт об ошибке, незачем устраивать вторую."""
    assert report.save(shift_ok, directory='/несуществующий/\x00путь') is None


def test_папка_отчётов_доступна_на_запись():
    path = report.reports_dir()
    assert os.path.isdir(path) and os.access(path, os.W_OK)
