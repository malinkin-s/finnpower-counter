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
from typing import List, Optional, Tuple

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
        raise ValueError('не удалось прочитать файл: {}'.format(last_error))

    candidates.sort()
    _, _, encoding, text = candidates[0]
    return normalize_newlines(text), encoding


def read_text(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Tuple[str, str]:
    """Прочитать файл. Возвращает (текст, имя выбранной кодировки)."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    return decode(raw, syntax)


def program_number(path: str, syntax: MachineSyntax = DEFAULT_SYNTAX) -> Optional[int]:
    """Номер программы из имени файла.

    Берётся именно номер: сортировка имён по алфавиту ставит PRG_10 перед
    PRG_9, и крайняя программа для детали определяется неверно.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    match = syntax.program_number.search(stem)
    return int(match.group(1)) if match else None
