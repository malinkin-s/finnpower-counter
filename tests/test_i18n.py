# -*- coding: utf-8 -*-
"""Переводы: полнота словарей и подстановка параметров."""

import re

import pytest

from finnpower_counter import i18n

PLACEHOLDER = re.compile(r'\{(\w+)\}')


def test_есть_оба_языка():
    assert set(i18n.available()) == {'en', 'ru'}


def test_запасной_язык_есть_в_словарях():
    assert i18n.FALLBACK in i18n.CATALOGS


@pytest.mark.parametrize('code', sorted(set(i18n.CATALOGS) - {i18n.FALLBACK}))
def test_словарь_полон(code):
    """Недостающий ключ показал бы пользователю чужой язык."""
    missing = sorted(set(i18n.CATALOGS[i18n.FALLBACK]) - set(i18n.CATALOGS[code]))
    assert missing == [], 'нет переводов: {}'.format(missing)


@pytest.mark.parametrize('code', sorted(i18n.CATALOGS))
def test_нет_лишних_ключей(code):
    extra = sorted(set(i18n.CATALOGS[code]) - set(i18n.CATALOGS[i18n.FALLBACK]))
    assert extra == [], 'ключи мимо английского словаря: {}'.format(extra)


@pytest.mark.parametrize('code', sorted(i18n.CATALOGS))
def test_подстановки_совпадают_с_английским(code):
    """Разный набор {параметров} даёт текст без подставленных значений."""
    base = i18n.CATALOGS[i18n.FALLBACK]
    for key, template in i18n.CATALOGS[code].items():
        assert set(PLACEHOLDER.findall(template)) == set(PLACEHOLDER.findall(base[key])), key


@pytest.mark.parametrize('code', sorted(i18n.CATALOGS))
def test_у_каждого_языка_есть_название(code):
    assert i18n.language_name(code) != code


def test_выбор_языка():
    assert i18n.set_language('ru') == 'ru'
    assert i18n.current() == 'ru'
    assert i18n.t('status.done') == 'Готово'
    assert i18n.set_language('en') == 'en'
    assert i18n.t('status.done') == 'Done'


@pytest.mark.parametrize('value', ['ru_RU', 'RU', 'ru-ru', ' ru '])
def test_код_языка_разбирается_свободно(value):
    assert i18n.set_language(value) == 'ru'


@pytest.mark.parametrize('value', ['de', 'zz', '', None])
def test_неизвестный_язык_даёт_запасной(value):
    assert i18n.set_language(value) == i18n.FALLBACK


def test_неизвестный_ключ_возвращается_как_есть():
    assert i18n.t('нет.такого.ключа') == 'нет.такого.ключа'


def test_лишние_параметры_не_ломают_перевод():
    assert i18n.t('status.done', чего='нибудь') == 'Готово'


def test_недостающий_параметр_не_роняет():
    """Лучше показать шаблон, чем уронить окно."""
    assert '{' in i18n.t('counters')


def test_подстановка_работает():
    text = i18n.t('counters', programs=30, parts=70, pieces=560, done=27, total=70)
    assert '30' in text and '560' in text and '27' in text


def test_определение_языка_из_окружения(monkeypatch):
    monkeypatch.setenv('LANGUAGE', 'ru_RU.UTF-8')
    assert i18n.detect() == 'ru'
    monkeypatch.setenv('LANGUAGE', 'en_US.UTF-8')
    assert i18n.detect() == 'en'


def test_пустая_локаль_не_считается_языком(monkeypatch):
    for name in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('LANG', 'C')
    assert i18n.detect() in i18n.available()
