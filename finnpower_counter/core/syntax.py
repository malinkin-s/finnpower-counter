# -*- coding: utf-8 -*-
"""Описание синтаксиса файлов станка.

Весь машинно-зависимый разбор собран здесь. Чтобы приспособить утилиту под
другое оборудование, достаточно собрать свой MachineSyntax — остальной код
не меняется.
"""

import dataclasses
import re
from typing import Dict, FrozenSet, Pattern, Tuple


@dataclasses.dataclass(frozen=True)
class MachineSyntax:
    """Как читать управляющую программу и отчёт наладки конкретного станка."""

    name: str

    # --- Управляющая программа (.nc) ---

    # Объявление числа листов. Обязательно с якорем на начало строки: в конце
    # программы имя SHEET_COUNT встречается ещё раз, в условии перехода
    # IF (SHEET_COUNT > R400) ... , и это не объявление.
    sheet_count: Pattern

    # Блок описания детали целиком. Разбор идёт по блокам, а не сквозным
    # поиском: ленивый поиск QUANTITY после PART_NAME на битом блоке
    # подхватит количество из следующего.
    part_block: Pattern

    # Поля внутри блока.
    part_name: Pattern
    quantity: Pattern

    # --- Отчёт наладки (.fms) ---

    fms_sheet_count: Pattern
    # Секция #RSCUT: одна строка на деталь, количество уже просуммировано.
    fms_rscut_part: Pattern
    # Секция #COMPONENTS: одна строка на блок. Пробелы вокруг "=" здесь
    # другие, чем в #RSCUT.
    fms_component_part: Pattern

    # --- Общее ---

    # Служебные контуры: обрезки, в учёт не идут.
    scrap_names: FrozenSet[str]

    # Номер программы из имени файла. Нужен именно номер, а не имя: сортировка
    # по алфавиту ставит PRG_10 перед PRG_9 и портит расчёт крайней программы.
    program_number: Pattern

    nc_suffixes: Tuple[str, ...]
    fms_suffixes: Tuple[str, ...]

    # Кодировки перебираются по порядку. Последняя должна быть такой, которая
    # не падает ни на каком байте, иначе файл нечем будет прочитать.
    encodings: Tuple[str, ...]

    def is_scrap(self, part_name: str) -> bool:
        return part_name.strip().upper() in self.scrap_names


NCEXPRESS_FMS = MachineSyntax(
    name='Prima Power / Finn-Power, постпроцессор NCeXpress FMS',

    sheet_count=re.compile(r'^[ \t]*SHEET_COUNT[ \t]*=[ \t]*(\d+)', re.MULTILINE),

    part_block=re.compile(
        r'^[ \t]*PART_DATA[ \t]*=[ \t]*\d+[ \t]*$(.*?)^[ \t]*SAVE_DATA[ \t]*$',
        re.MULTILINE | re.DOTALL),
    part_name=re.compile(r'^[ \t]*PART_NAME[ \t]*=[ \t]*"([^"]*)"', re.MULTILINE),
    quantity=re.compile(r'^[ \t]*QUANTITY[ \t]*=[ \t]*(\d+)', re.MULTILINE),

    fms_sheet_count=re.compile(r'^NUMBER OF SHEETS[ \t]*:[ \t]*(\d+)', re.MULTILINE),
    fms_rscut_part=re.compile(
        r'^(\S+)[ \t]*:[ \t]*Size[ \t]+[\d.]+[ \t]*x[ \t]*[\d.]+,[ \t]*Number=(\d+)',
        re.MULTILINE),
    fms_component_part=re.compile(
        r'^\(\d+\)[ \t]*(\S+)[ \t]*:[ \t]*Size[ \t]+[\d.]+[ \t]*x[ \t]*[\d.]+,'
        r'[ \t]*Number[ \t]*=[ \t]*(\d+)',
        re.MULTILINE),

    scrap_names=frozenset({'SCRAP'}),

    program_number=re.compile(r'(\d+)(?!.*\d)'),

    nc_suffixes=('.nc',),
    fms_suffixes=('.fms',),

    encodings=('utf-8', 'utf-8-sig', 'cp1251', 'cp866', 'latin-1'),
)

DEFAULT_SYNTAX = NCEXPRESS_FMS

# Секции .fms, между которыми лежат нужные строки.
FMS_SECTIONS: Dict[str, str] = {
    'rscut': '#RSCUT',
    'components': '#COMPONENTS',
}
