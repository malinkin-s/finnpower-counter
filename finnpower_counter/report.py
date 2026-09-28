# -*- coding: utf-8 -*-
"""Отчёты об ошибках.

Задача — дать оператору файл, который не стыдно приложить к issue, и при этом
не вынести наружу заводские данные. Поэтому отчёт обезличен по построению:
имена программ заменяются на PRG_NN, наименования деталей на PART_NN, пути
урезаются до имени файла. Подстановки устойчивы в пределах отчёта, так что
по нему видно, какая программа с какой связана, но не какие это детали.

Отчёт остаётся на диске: интернета на цеховом компьютере нет, отправить
его некуда. Оператор передаёт файл, как ему удобно.
"""

import os
import platform
import re
import sys
import tempfile
import traceback
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from . import __version__, i18n
from .core.model import ShiftSummary

APP_DIR_NAME = 'FinnPowerCounter'
FILE_PREFIX = 'report'

# Пути: и виндовые, и юниксовые. Оставляем только имя файла.
# Виндовый путь тянется до кавычки или конца строки, а не до пробела: в именах
# папок пробелы обычны («Ivan Petrov», «Общая папка»), и обрыв на пробеле
# оставлял в отчёте хвост пути вместе с фамилией. Лишнее съеденное после пути
# безвредно, недосъеденное — утечка.
_WINDOWS_PATH = re.compile(r'[A-Za-z]:\\[^"\'<>|\r\n]+')
_POSIX_PATH = re.compile(r'/(?:[\w.\- ]+/)+[\w.\-]+')
# Сетевые папки вида \\SERVER\SHARE\...
_UNC_PATH = re.compile(r'\\{2,}[^\s\\"\'<>|]+\\[^"\'<>|\r\n]*')

# Имена файлов, которые можно оставить: исходники утилиты и уже обезличенные
# PRG_NN / PART_NN. Остальное — имя программы или чертежа, оно заменяется.
_SAFE_NAME = re.compile(r'^(?:[\w\-]+\.pyw?|(?:PRG|PART)_\d+(?:\.\w+)?)$')
_EXTENSION = re.compile(r'\.[A-Za-z0-9]{1,5}$')


class Scrubber:
    """Замена заводских обозначений на нейтральные."""

    def __init__(self,
                 programs: Iterable[str] = (),
                 parts: Iterable[str] = ()) -> None:
        self._map: Dict[str, str] = {}
        for index, name in enumerate(sorted(set(programs)), start=1):
            self._map[name] = 'PRG_{:02d}'.format(index)
        for index, name in enumerate(sorted(set(parts)), start=1):
            self._map[name] = 'PART_{:02d}'.format(index)
        # Длинные первыми: иначе короткое имя съест часть длинного.
        self._order = sorted(self._map, key=len, reverse=True)

    def alias(self, name: str) -> str:
        return self._map.get(name, name)

    def text(self, value: Any) -> str:
        """Обезличить произвольный текст: сначала имена, потом пути."""
        text = str(value)
        for name in self._order:
            if name:
                text = text.replace(name, self._map[name])
        return scrub_paths(text)


def scrub_paths(text: str) -> str:
    """Оставить от пути только имя файла.

    Путь выдаёт и предприятие, и фамилию пользователя, и структуру сети.
    Для разбора ошибки достаточно имени файла.

    Само имя тоже может выдать заводское обозначение: если отчёт собирается
    без задания, подстановке PRG_NN не из чего строиться. Поэтому имя
    остаётся, только если оно заведомо безопасно, иначе от него остаётся
    расширение: FILE.nc.
    """
    def keep_name(match: 're.Match') -> str:
        raw = match.group(0)
        name = re.split(r'[\\/]', raw)[-1]
        if name and not _SAFE_NAME.match(name):
            extension = _EXTENSION.search(name)
            name = 'FILE' + (extension.group(0) if extension else '')
        return '...' + ('/' + name if name else '')

    text = _WINDOWS_PATH.sub(keep_name, text)
    text = _UNC_PATH.sub(keep_name, text)
    return _POSIX_PATH.sub(keep_name, text)


def reports_dir() -> str:
    """Куда класть отчёты.

    Рядом с исполняемым файлом писать нельзя: на цеховой машине папка может
    быть только для чтения и прав администратора нет. Берём пользовательскую
    папку, а если и она недоступна — временную.
    """
    candidates: List[str] = []
    if sys.platform.startswith('win'):
        base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA')
        if base:
            candidates.append(os.path.join(base, APP_DIR_NAME))
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
        candidates.append(os.path.join(base, 'finnpower-counter'))
    candidates.append(os.path.join(tempfile.gettempdir(), APP_DIR_NAME))

    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, '.probe')
            with open(probe, 'w'):
                pass
            os.remove(probe)
            return path
        except OSError:
            continue
    return tempfile.gettempdir()


def environment() -> List[str]:
    """Сведения о среде. Имя машины и пользователя сюда не идут."""
    return [
        'Версия утилиты : {}'.format(__version__),
        'Python         : {}'.format(sys.version.split()[0]),
        'Система        : {} {}'.format(platform.system(), platform.release()),
        'Разрядность    : {}'.format(platform.architecture()[0]),
        'Сборка         : {}'.format(
            'исполняемый файл' if getattr(sys, 'frozen', False) else 'исходник'),
        'Язык интерфейса: {}'.format(i18n.current()),
    ]


def shift_outline(summary: Optional[ShiftSummary],
                  scrubber: Scrubber) -> List[str]:
    """Скелет сменного задания: структура без заводских обозначений.

    По нему ошибка воспроизводится синтетическим набором, а что за детали
    и чей это заказ — из отчёта не следует.
    """
    if summary is None:
        return ['Папка со сменным заданием не была открыта.']

    lines = [
        'Программ       : {} (пригодных {})'.format(
            len(summary.programs), len(summary.usable_programs)),
        'Позиций        : {}'.format(summary.unique_parts),
        'Деталей        : {}'.format(summary.total_pieces),
        '',
        'Программы (место, листов, позиций, деталей):',
    ]
    for nest in summary.programs:
        lines.append('  {:>3}  {:<10} листов={:<4} позиций={:<4} деталей={}'.format(
            nest.position, scrubber.alias(nest.name),
            '?' if nest.sheet_count is None else nest.sheet_count,
            nest.unique_parts, nest.total_pieces))

    if summary.warnings:
        lines += ['', 'Замечания разбора:']
        counts: Dict[str, int] = {}
        for note in summary.warnings:
            counts[note.key] = counts.get(note.key, 0) + 1
        for key in sorted(counts):
            lines.append('  {} — {} раз'.format(key, counts[key]))
    return lines


def build(summary: Optional[ShiftSummary] = None,
          exc_info: Optional[tuple] = None,
          actions: Iterable[str] = ()) -> str:
    """Собрать текст отчёта."""
    scrubber = Scrubber(
        programs=[n.name for n in summary.programs] if summary else (),
        parts=[p.part for p in summary.parts] if summary else ())

    lines = [
        '=' * 62,
        'Отчёт утилиты учёта готовности деталей',
        'Создан: {}'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        '=' * 62,
        '',
        'ЧТО ЗА ФАЙЛ',
        '  Обозначения программ и деталей заменены на PRG_NN и PART_NN,',
        '  пути урезаны до имени файла. Заводских данных здесь нет,',
        '  файл можно прикладывать к сообщению об ошибке.',
        '',
        'СРЕДА',
    ]
    lines += ['  ' + line for line in environment()]

    if exc_info is not None:
        lines += ['', 'ОШИБКА']
        text = ''.join(traceback.format_exception(*exc_info))
        lines += ['  ' + scrubber.text(line)
                  for line in text.rstrip().splitlines()]

    actions = list(actions)
    if actions:
        lines += ['', 'ПОСЛЕДНИЕ ДЕЙСТВИЯ']
        lines += ['  ' + scrubber.text(item) for item in actions]

    lines += ['', 'СМЕННОЕ ЗАДАНИЕ']
    lines += ['  ' + line for line in shift_outline(summary, scrubber)]

    lines += [
        '',
        'ЧТО ДОПИСАТЬ ВРУЧНУЮ',
        '  1. Что вы делали перед тем, как это случилось.',
        '  2. Что ожидали увидеть и что увидели.',
        '  3. Если расходятся цифры — какие именно и с чем сверяли.',
        '',
    ]
    return '\n'.join(lines)


def save(summary: Optional[ShiftSummary] = None,
         exc_info: Optional[tuple] = None,
         actions: Iterable[str] = (),
         directory: Optional[str] = None) -> Optional[str]:
    """Записать отчёт. Возвращает путь или None, если записать не удалось.

    Исключения наружу не выпускаются: не сумев сохранить отчёт об ошибке,
    незачем устраивать вторую ошибку.
    """
    try:
        target = directory or reports_dir()
        os.makedirs(target, exist_ok=True)
        name = '{}-{}.txt'.format(FILE_PREFIX,
                                  datetime.now().strftime('%Y%m%d-%H%M%S'))
        path = os.path.join(target, name)
        with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
            fh.write(build(summary, exc_info, actions))
        return path
    except Exception:
        return None
