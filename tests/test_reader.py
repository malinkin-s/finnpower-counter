# -*- coding: utf-8 -*-
"""Чтение файлов в разных кодировках."""

import os

import pytest

from finnpower_counter.core import reader

COMMENT = 'Наладка выполнена, лист 2 мм'
SAMPLE = '; {}\nSHEET_COUNT=1\n'.format(COMMENT)


@pytest.mark.parametrize('encoding', ['utf-8', 'cp1251', 'cp866'])
def test_кириллица_читается_в_своей_кодировке(encoding):
    """Однобайтовые кодировки принимают почти любой байт, поэтому выбор идёт
    не по «первая не упала», а по осмысленности результата."""
    text, detected = reader.decode(SAMPLE.encode(encoding))
    assert COMMENT in text
    assert detected == encoding


def test_bom_не_попадает_в_текст():
    text, _ = reader.decode(SAMPLE.encode('utf-8-sig'))
    assert text.startswith('; ')


@pytest.mark.parametrize('newline', ['\n', '\r\n', '\r'])
def test_переводы_строк_приводятся_к_lf(newline):
    text, _ = reader.decode(SAMPLE.replace('\n', newline).encode('utf-8'))
    assert '\r' not in text


def test_произвольные_байты_не_роняют_чтение():
    text, encoding = reader.decode(bytes(range(256)))
    assert isinstance(text, str)
    assert encoding


def test_пустой_файл():
    assert reader.decode(b'') == ('', 'utf-8')


def test_кодировки_краевых_файлов(edge_dir):
    expected = {'cp1251.nc': 'cp1251', 'cp866.nc': 'cp866', 'crlf.nc': 'utf-8'}
    for name, encoding in expected.items():
        _, detected = reader.read_text(os.path.join(edge_dir, name))
        assert detected == encoding, name
