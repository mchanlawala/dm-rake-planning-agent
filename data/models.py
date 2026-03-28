# data/models.py
"""
Data Models for Rake Planning System
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class Category(Enum):
    """Width category enumeration"""
    NARROW = "NARROW"
    WIDER = "WIDER"
    EXTRA = "EXTRA"
    OTHER = "OTHER"


@dataclass
class Coil:
    """Represents a steel coil"""
    batch_number: str
    order_number: str
    order_line: str
    stock_weight: float
    stock_width: float
    stock_length: float
    location: str
    group_id: int = None
    wagon_id: int = None

    @property
    def category(self) -> Category:
        """Determine width category"""
        if 900 <= self.stock_width <= 1199:
            return Category.NARROW
        elif 1200 <= self.stock_width <= 1499:
            return Category.WIDER
        elif 1500 <= self.stock_width <= 2000:
            return Category.EXTRA
        else:
            return Category.OTHER


@dataclass
class RakeType:
    """Rake configuration"""
    type_id: int
    name: str
    min_weight: float
    max_weight: float
    total_capacity: float
    no_wagons: int

    def get_target_weight(self) -> float:
        """Get target weight per wagon"""
        return (self.min_weight + self.max_weight) / 2


@dataclass
class Wagon:
    """Represents a wagon"""
    id: int
    location: str
    coils: List[Coil] = None
    total_weight: float = 0.0

    def __post_init__(self):
        if self.coils is None:
            self.coils = []

    @property
    def narrow_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.NARROW)

    @property
    def wider_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.WIDER)

    @property
    def extra_count(self) -> int:
        return sum(1 for c in self.coils if c.category == Category.EXTRA)

    def can_add_coil(self, coil: Coil, rake: RakeType, max_coils_per_wagon: int = 4) -> Tuple[bool, str]:
        """Check if coil can be added to wagon"""
        # Location constraint
        if self.coils and self.location != coil.location:
            return False, "Location mismatch"

        # Category count constraints
        if coil.category == Category.NARROW and self.narrow_count >= 4:
            return False, "Max narrow coils (4) reached"
        if coil.category == Category.WIDER and self.wider_count >= 3:
            return False, "Max wider coils (3) reached"
        if coil.category == Category.EXTRA and self.extra_count >= 2:
            return False, "Max extra coils (2) reached"

        # Weight constraint
        new_weight = self.total_weight + coil.stock_weight
        if new_weight > rake.max_weight:
            return False, f"Weight limit exceeded"

        # Total coils constraint
        if len(self.coils) >= max_coils_per_wagon:
            return False, f"Max {max_coils_per_wagon} coils per wagon"

        return True, "OK"

    def add_coil(self, coil: Coil, rake: RakeType, max_coils_per_wagon: int = 4) -> bool:
        """Add coil to wagon if possible"""
        can_add, _ = self.can_add_coil(coil, rake, max_coils_per_wagon)
        if can_add:
            if not self.coils:
                self.location = coil.location
            self.coils.append(coil)
            self.total_weight += coil.stock_weight
            return True
        return False

    @property
    def is_valid_combination(self, valid_combinations: List[Tuple[int, int, int]]) -> bool:
        """Check if wagon follows allowed combinations"""
        n, w, e = self.narrow_count, self.wider_count, self.extra_count
        total = n + w + e

        if total == 0:
            return True

        return (n, w, e) in valid_combinations