# -*- coding: utf-8 -*-
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@pytest.fixture(scope='session')
def fixtures_dir():
    return FIXTURES


@pytest.fixture(scope='session')
def expected():
    """Эталонный свод, посчитанный генератором из описания смены."""
    with open(os.path.join(FIXTURES, 'expected.json'), encoding='utf-8') as fh:
        return json.load(fh)


@pytest.fixture(scope='session')
def shift_ok():
    from finnpower_counter.core import balance
    return balance.load_shift(os.path.join(FIXTURES, 'shift_ok'))


@pytest.fixture(scope='session')
def edge_dir():
    return os.path.join(FIXTURES, 'edge')
