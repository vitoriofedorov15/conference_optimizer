"""
Модели данных для модуля оптимизации выдачи конференций.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Conference:
    """Один выпуск (экземпляр) конференции."""
    conf_id:    int
    conf_name:  str
    year:       Optional[int]  = None
    location:   Optional[str]  = None
    base_name:  str            = ''
    series_key: str            = ''
    key_type:   str            = 'name'   # 'abbr' | 'title' | 'name'

    def __repr__(self):
        return (f"Conference(id={self.conf_id}, "
                f"key='{self.series_key}', year={self.year})")


@dataclass
class ConferenceSeries:
    """Серия конференций — объединение выпусков по одному ключу."""
    base_name: str
    key_type:  str            = 'name'
    editions:  List           = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.editions)

    @property
    def years(self) -> List[int]:
        return sorted(e.year for e in self.editions if e.year is not None)

    @property
    def year_range(self) -> Optional[str]:
        y = self.years
        if not y:
            return None
        return str(y[0]) if len(y) == 1 else f'{y[0]}–{y[-1]}'

    def display_name(self) -> str:
        """Человекочитаемое название серии."""
        # Для аббревиатур — берём самое длинное исходное название как описание
        if self.key_type == 'abbr':
            # Находим наиболее полное оригинальное название
            candidates = [e.conf_name for e in self.editions if e.conf_name]
            if candidates:
                longest = max(candidates, key=len)
                return longest
        return self.base_name

    def to_dict(self) -> dict:
        return {
            'series_key':     self.base_name,
            'key_type':       self.key_type,
            'editions_count': self.count,
            'year_range':     self.year_range,
            'editions': [
                {
                    'conf_id':   e.conf_id,
                    'conf_name': e.conf_name,
                    'base_name': e.base_name,
                    'year':      e.year,
                    'location':  e.location,
                }
                for e in sorted(self.editions, key=lambda x: x.year or 0, reverse=True)
            ],
        }

    def __repr__(self):
        return (f"ConferenceSeries(key='{self.base_name}', "
                f"type='{self.key_type}', editions={self.count}, "
                f"years={self.year_range})")
