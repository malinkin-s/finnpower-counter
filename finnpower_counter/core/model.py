# -*- coding: utf-8 -*-
"""Модель данных: программа, итог по позиции, состояние смены."""

import dataclasses
from typing import Dict, List, Optional

STATUS_DONE = 'Готово'
STATUS_IN_WORK = 'В работе'


@dataclasses.dataclass
class ProgramNest:
    """Одна управляющая программа: сколько листов и что на листе.

    parts_per_sheet — количество на ОДНОМ листе, уже просуммированное по всем
    блокам PART_DATA этой детали. Тираж в программе даёт pieces().
    """

    number: int
    name: str
    path: str
    sheet_count: Optional[int]
    parts_per_sheet: Dict[str, int] = dataclasses.field(default_factory=dict)
    warnings: List[str] = dataclasses.field(default_factory=list)

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


@dataclasses.dataclass
class PartTotal:
    """Итог по позиции за смену."""

    part: str
    total: int
    last_program: int
    by_program: Dict[int, int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ShiftSummary:
    """Свод сменного задания."""

    programs: List[ProgramNest] = dataclasses.field(default_factory=list)
    parts: List[PartTotal] = dataclasses.field(default_factory=list)
    warnings: List[str] = dataclasses.field(default_factory=list)

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
    def program_numbers(self) -> List[int]:
        return [p.number for p in self.usable_programs]


@dataclasses.dataclass
class PartStatus:
    """Состояние позиции на момент, когда выполнены программы по номер done."""

    part: str
    total: int
    last_program: int
    produced: int

    @property
    def is_complete(self) -> bool:
        return self.produced >= self.total

    @property
    def remaining(self) -> int:
        return self.total - self.produced

    @property
    def status(self) -> str:
        return STATUS_DONE if self.is_complete else STATUS_IN_WORK


@dataclasses.dataclass
class CrossCheckResult:
    """Сверка разбора .nc с отчётом наладки .fms."""

    checked: int = 0
    skipped: int = 0
    mismatches: List[str] = dataclasses.field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.checked > 0 and not self.mismatches
