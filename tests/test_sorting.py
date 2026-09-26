# -*- coding: utf-8 -*-
"""Порядок программ.

Имена без ведущих нулей сортируются по алфавиту как PRG_1, PRG_10, PRG_11,
PRG_2, и крайняя программа позиции определяется неверно. Учёт должен идти
по номеру.
"""

import os

from finnpower_counter.core import balance, reader


def test_номер_читается_из_имени():
    assert reader.program_number('PRG_07.nc') == 7
    assert reader.program_number('PRG_9.nc') == 9
    assert reader.program_number('/цех/смена/PRG_30.NC') == 30
    assert reader.program_number('без-номера.nc') is None


def test_алфавит_и_номер_дают_разный_порядок(fixtures_dir):
    names = [n for n in os.listdir(os.path.join(fixtures_dir, 'unpadded'))
             if n.endswith('.nc')]
    by_name = sorted(names)
    by_number = sorted(names, key=lambda n: reader.program_number(n))
    assert by_name != by_number, 'набор должен ловить ловушку сортировки'


def test_свод_не_зависит_от_ведущих_нулей(fixtures_dir, expected):
    summary = balance.load_shift(os.path.join(fixtures_dir, 'unpadded'))
    got = [{'part': p.part, 'total': p.total, 'last_program': p.last_program}
           for p in summary.parts]
    assert got == expected['parts']


def test_программы_идут_по_возрастанию_номера(fixtures_dir):
    summary = balance.load_shift(os.path.join(fixtures_dir, 'unpadded'))
    numbers = [p.number for p in summary.programs]
    assert numbers == sorted(numbers)
