# -*- coding: utf-8 -*-
"""Обращения к операционной системе.

Здесь единственное место, где утилита выходит за пределы чтения файлов:
открытие карты наладки той программой, которая назначена в системе.
"""

import os
import subprocess
import sys
from typing import Optional


def open_folder(path: str) -> Optional[str]:
    """Открыть папку в проводнике. Возвращает None при успехе или текст ошибки."""
    return _launch(path, os.path.isdir)


def open_document(path: str) -> Optional[str]:
    """Открыть файл назначенным в системе приложением.

    Возвращает None при успехе или текст ошибки. Исключения не выпускаются
    наружу: не открывшийся PDF не повод ронять окно оператора.
    """
    return _launch(path, os.path.isfile)


def _launch(path: str, exists) -> Optional[str]:
    if not path or not exists(path):
        return 'not found: {}'.format(path)
    try:
        if sys.platform.startswith('win'):
            # os.startfile есть только на Windows — целевой платформе.
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
    except Exception as exc:
        return '{}: {}'.format(type(exc).__name__, exc)
    return None
