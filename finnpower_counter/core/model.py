# -*- coding: utf-8 -*-
"""Модель данных: программа, итог по позиции, состояние смены."""

import dataclasses
from typing import Any, Dict, List, Optional

from .. import i18n

# Коды, а не подписи: перевод на язык интерфейса делает presentation.
STATUS_DONE = 'done'
STATUS_IN_WORK = 'in_work'


@dataclasses.dataclass(frozen=True)
class Note:
    """Замечание разбора.

    Хранится ключом и параметрами, а не готовой строкой: язык интерфейса
    может смениться уже после того, как файлы разобраны.
    """

    key: str
    params: Dict[str, Any] = dataclasses.field(default_factory=dict)
    program: Optional[str] = None

    def text(self) -> str:
        body = i18n.t(self.key, **self.params)
        return '{}: {}'.format(self.program, body) if self.program else body

    def __str__(self) -> str:
        return self.text()

    def with_program(self, program: str) -> 'Note':
        return Note(key=self.key, params=self.params, program=program)


@dataclasses.dataclass
class ProgramNest:
    """Одна управляющая программа: сколько листов и что на листе.

    parts_per_sheet — количество на ОДНОМ листе, уже просуммированное по всем
    блокам PART_DATA этой детали. Тираж в программе даёт pieces().

    position — место в сменном задании, от 1. Именно оно задаёт порядок
    выполнения и по нему считается крайняя программа позиции. number —
    справочное число из имени файла, для расчётов негодное: на именах
    с датой оно не возрастает и не уникально.
    """

    position: int
    number: Optional[int]
    name: str
    path: str
    sheet_count: Optional[int]
    sheet_x: Optional[float] = None
    sheet_y: Optional[float] = None
    parts_per_sheet: Dict[str, int] = dataclasses.field(default_factory=dict)
    warnings: List[Note] = dataclasses.field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """Можно ли считать по этой программе.

        Без числа листов тираж неизвестен. Молча подставлять единицу нельзя:
        расчёт уйдёт в ошибку тихо, а утилита нужна ровно чтобы этого не было.
        """
        return self.sheet_count is not None

    def pieces(self) -> Dict[str, int]:
        """Тираж каждой детали в этой программе: листы * количество на листе."""
        if self.sheet_count is None:
            return {}
        return {name: qty * self.sheet_count
                for name, qty in self.parts_per_sheet.items()}

    @property
    def total_pieces(self) -> int:
        return sum(self.pieces().values())

    @property
    def unique_parts(self) -> int:
        return len(self.parts_per_sheet)

    @property
    def sheet_size(self) -> str:
        """Габариты листа для показа: «2500 x 1250». Дробная часть убирается,
        если она нулевая — в файлах размеры обычно целые."""
        if self.sheet_x is None or self.sheet_y is None:
            return ''
        def fmt(value: float) -> str:
            return str(int(value)) if float(value).is_integer() else str(value)
        return '{} x {}'.format(fmt(self.sheet_x), fmt(self.sheet_y))


@dataclasses.dataclass
class PartTotal:
    """Итог по позиции за смену.

    last_position — место крайней программы в задании, для сравнений.
    last_program — её имя, для показа. by_program — тираж по местам задания.
    """

    part: str
    total: int
    last_position: int
    last_program: str
    by_program: Dict[int, int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ShiftSummary:
    """Свод сменного задания."""

    programs: List[ProgramNest] = dataclasses.field(default_factory=list)
    parts: List[PartTotal] = dataclasses.field(default_factory=list)
    warnings: List[Note] = dataclasses.field(default_factory=list)

    @property
    def usable_programs(self) -> List[ProgramNest]:
        return [p for p in self.programs if p.is_usable]

    @property
    def unique_parts(self) -> int:
        return len(self.parts)

    @property
    def total_pieces(self) -> int:
        return sum(p.total for p in self.parts)

    @property
    def positions(self) -> List[int]:
        return [p.position for p in self.usable_programs]

    def by_position(self, position: int) -> Optional[ProgramNest]:
        for nest in self.programs:
            if nest.position == position:
                return nest
        return None


@dataclasses.dataclass
class PartStatus:
    """Состояние позиции, когда выполнены программы по место done."""

    part: str
    total: int
    last_position: int
    last_program: str
    produced: int

    @property
    def is_complete(self) -> bool:
        return self.produced >= self.total

    @property
    def remaining(self) -> int:
        return self.total - self.produced

    @property
    def status(self) -> str:
        """Код статуса. Подпись для показа даёт presentation.status_text."""
        return STATUS_DONE if self.is_complete else STATUS_IN_WORK


@dataclasses.dataclass
class CrossCheckResult:
    """Сверка разбора .nc с отчётом наладки .fms."""

    checked: int = 0
    skipped: int = 0
    mismatches: List[Note] = dataclasses.field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.checked > 0 and not self.mismatches
