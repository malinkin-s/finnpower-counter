# -*- coding: utf-8 -*-
"""Чтение текстовых файлов станка.

Файлы приходят из разных источников и сохраняются в разных кодировках и с
разными переводами строк. Упасть на чтении утилита не имеет права.

Про выбор кодировки. Однобайтовые кодировки принимают почти любой байт, и
правило «берём первую, которая не упала» даёт cp1251 для всего подряд. Поэтому
вариант выбирается по тому, насколько осмысленным получился текст. На сам учёт
это не влияет — имена деталей и количества записаны латиницей и цифрами, —
но кириллица в комментариях наладчика должна читаться верно.
"""

import os
import re
from typing import Any, List, Optional, Tuple

from .. import i18n
from .syntax import DEFAULT_SYNTAX, MachineSyntax

# Символы, ожидаемые в файле станка: латиница, цифры, знаки препинания,
# кириллица в комментариях.
_EXPECTED = set(
    'abcdefghijklmnopqrstuvwxyz'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '0123456789'
    ' \t\r\n'
    '!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
    'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'
    '°±×'
)


def normalize_newlines(text: str) -> str:
    """Привести переводы строк к \\n.

    Иначе \\r остаётся в конце строки, и регулярные выражения с якорем на
    конец строки перестают срабатывать: блоки PART_DATA просто не находятся.
    """
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _plausibility(text: str) -> float:
    """Доля символов, уместных в файле станка. 1.0 — весь текст осмыслен."""
    if not text:
        return 1.0
    good = sum(1 for char in text if char in _EXPECTED)
    return good / float(len(text))


def decode(raw: bytes, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Tuple[str, str]:
    """Декодировать байты. Возвращает (текст, имя выбранной кодировки).

    Переводы строк приводятся к \\n: иначе \\r остаётся в конце строки и
    регулярные выражения с якорем на конец строки перестают срабатывать.
    """
    candidates: List[Tuple[float, int, str, str]] = []
    last_error: Optional[Exception] = None

    for order, encoding in enumerate(syntax.encodings):
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
            continue
        score = _plausibility(text)
        # При равном качестве побеждает кодировка, стоящая в списке раньше.
        candidates.append((-score, order, encoding, text))
        # Текст полностью осмыслен — дальше перебирать нечего.
        if score == 1.0:
            break

    if not candidates:  # pragma: no cover - недостижимо, пока в списке есть latin-1
        raise ValueError(i18n.t('error.unreadable', details=last_error))

    candidates.sort()
    _, _, encoding, text = candidates[0]
    return normalize_newlines(text), encoding


def read_text(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Tuple[str, str]:
    """Прочитать файл. Возвращает (текст, имя выбранной кодировки)."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    return decode(raw, syntax)


def search_float(pattern, text: str) -> Optional[float]:
    """Первое число по шаблону или None. Для габаритов листа в .nc и .fms."""
    found = pattern.search(text)
    return float(found.group(1)) if found else None


def find_sibling(path: str, suffixes: Tuple[str, ...]) -> Optional[str]:
    """Найти рядом с файлом однофамильца с другим расширением.

    Регистр расширения на разных системах разный: файлы могли прийти
    с Windows, где PRG_07.PDF и PRG_07.pdf — одно и то же.
    """
    stem = os.path.splitext(path)[0]
    for suffix in suffixes:
        for candidate in (stem + suffix, stem + suffix.upper(),
                          stem + suffix.lower()):
            if os.path.isfile(candidate):
                return candidate
    return None


_DIGITS = re.compile(r'(\d+)')


def natural_key(path: str) -> Tuple[Any, ...]:
    """Ключ естественной сортировки имени файла.

    Порядок выполнения программ определяется именно так, а не по числу,
    выдернутому из имени. Причина в том, что одно число обе задачи не решает:

    * при сортировке по алфавиту PRG_10 встаёт перед PRG_9;
    * если брать последнюю группу цифр, то на именах вида ДДММГГ + код +
      номер (000101zz201001) последовательность получается ни возрастающей,
      ни уникальной: программы разных дат дают одинаковый хвост.

    Разбиение на числовые и текстовые куски с числовым сравнением чисел
    разбирает все три случая: с ведущими нулями, без них и с датой в имени.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    return tuple(int(part) if part.isdigit() else part.lower()
                 for part in _DIGITS.split(stem))


def program_number(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Optional[int]:
    """Число из имени файла, если оно там есть.

    Справочное значение. Для порядка выполнения не годится — см. natural_key.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    match = syntax.program_number.search(stem)
    return int(match.group(1)) if match else None
