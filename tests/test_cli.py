# -*- coding: utf-8 -*-
"""Консольный интерфейс."""

import io
import json
import os

import pytest

from finnpower_counter import cli, presentation


def run(argv, lang='ru'):
    """Запустить CLI, вернуть (код возврата, stdout, stderr).

    Язык задаётся явно: без него CLI берёт язык системы, и тесты зависели бы
    от машины, на которой запускаются.
    """
    argv = list(argv)
    if lang and not any(a == '--lang' or a.startswith('--lang=') for a in argv):
        argv += ['--lang', lang]
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def shift_dir(fixtures_dir):
    return os.path.join(fixtures_dir, 'shift_ok')


def test_исправная_смена_возвращает_ноль(shift_dir):
    code, out, err = run(['--dir', shift_dir, '--done', '9'])
    assert code == cli.EXIT_OK
    assert err == ''
    assert 'Готово полностью: 7 из 14' in out


def test_без_номера_программы_смена_не_начата(shift_dir):
    code, out, _ = run(['--dir', shift_dir])
    assert code == cli.EXIT_OK
    assert 'смена не начата' in out
    assert 'Готово полностью: 0 из 14' in out


def test_таблица_содержит_все_колонки(shift_dir):
    _, out, _ = run(['--dir', shift_dir, '--done', '5'])
    for column in presentation.columns():
        assert column in out


def test_отбор_только_готовых(shift_dir):
    _, out, _ = run(['--dir', shift_dir, '--done', '9', '--only', 'done'])
    assert 'В работе' not in out
    assert 'Готово' in out


def test_отбор_только_в_работе(shift_dir):
    _, out, _ = run(['--dir', shift_dir, '--done', '9', '--only', 'work'])
    lines = [l for l in out.splitlines() if l.startswith('PART_')]
    assert lines
    assert all('В работе' in l for l in lines)


def test_поиск_по_части_имени(shift_dir):
    _, out, _ = run(['--dir', shift_dir, '--done', '12', '--search', 'no13'])
    lines = [l for l in out.splitlines() if l.startswith('PART_')]
    assert len(lines) == 1
    assert 'PART_NO13' in lines[0]


def test_поиск_без_совпадений(shift_dir):
    code, out, _ = run(['--dir', shift_dir, '--search', 'ничего-такого'])
    assert code == cli.EXIT_OK
    assert 'ничего не подошло' in out


def test_итог_считается_по_всей_смене_а_не_по_отбору(shift_dir):
    """Отбор меняет показ, но не общую готовность."""
    _, full, _ = run(['--dir', shift_dir, '--done', '9'])
    _, filtered, _ = run(['--dir', shift_dir, '--done', '9', '--only', 'done'])
    assert 'Готово полностью: 7 из 14' in full
    assert 'Готово полностью: 7 из 14' in filtered


def test_json_разбирается_и_сходится_с_эталоном(shift_dir, expected):
    code, out, _ = run(['--dir', shift_dir, '--done', '12', '--json'])
    assert code == cli.EXIT_OK
    payload = json.loads(out)
    assert payload['unique_parts'] == expected['unique_parts']
    assert payload['total_pieces'] == expected['total_pieces']
    assert payload['programs'] == expected['programs']
    assert all(part['complete'] for part in payload['parts'])


def test_json_со_сверкой(shift_dir):
    _, out, _ = run(['--dir', shift_dir, '--validate', '--json'])
    payload = json.loads(out)
    assert payload['cross_check']['checked'] == 12
    assert payload['cross_check']['mismatches'] == []


def test_сверка_в_таблице(shift_dir):
    code, out, _ = run(['--dir', shift_dir, '--done', '12', '--validate'])
    assert code == cli.EXIT_OK
    assert 'расхождений нет' in out


def test_нет_папки_возвращает_ошибку():
    code, out, err = run(['--dir', os.path.join('нет', 'такой', 'папки')])
    assert code == cli.EXIT_ERROR
    assert out == ''
    assert 'Ошибка' in err


def test_пустая_папка_возвращает_ошибку(tmp_path):
    code, _, err = run(['--dir', str(tmp_path)])
    assert code == cli.EXIT_ERROR
    assert 'Ошибка' in err


def test_замечания_дают_отдельный_код(edge_dir):
    code, out, _ = run(['--dir', edge_dir, '--done', '1'])
    assert code == cli.EXIT_WARNINGS
    assert 'Замечания при разборе' in out


def test_вывод_переживает_узкую_кодировку_консоли(shift_dir):
    """Консоль Windows 7 — cp866. Расчёт не должен падать из-за вывода."""
    class AsciiStream(io.StringIO):
        encoding = 'ascii'

        def write(self, text):
            text.encode('ascii')  # как настоящий поток — бросит на кириллице
            return super(AsciiStream, self).write(text)

    out, err = AsciiStream(), AsciiStream()
    assert cli.main(['--dir', shift_dir, '--done', '5'], stdout=out, stderr=err) == cli.EXIT_OK
    assert 'PART_NO01' in out.getvalue()


def test_язык_задаётся_ключом(shift_dir):
    _, ru, _ = run(['--dir', shift_dir, '--done', '9'], lang='ru')
    _, en, _ = run(['--dir', shift_dir, '--done', '9'], lang='en')
    assert 'Готово' in ru and 'Готово' not in en
    assert 'Done' in en and 'Done' not in ru


def test_колонки_переводятся(shift_dir):
    from finnpower_counter import i18n
    _, en, _ = run(['--dir', shift_dir, '--done', '5'], lang='en')
    i18n.set_language('en')
    try:
        for column in presentation.columns():
            assert column in en
    finally:
        i18n.set_language('ru')


def test_замечания_переводятся(edge_dir):
    _, ru, _ = run(['--dir', edge_dir, '--done', '1'], lang='ru')
    _, en, _ = run(['--dir', edge_dir, '--done', '1'], lang='en')
    assert 'Замечания при разборе' in ru
    assert 'Notes from parsing' in en
