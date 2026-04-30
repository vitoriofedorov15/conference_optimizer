from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Conference:
    conf_id:    int
    conf_name:  str
    year:       Optional[int] = None
    location:   Optional[str] = None
    base_name:  str           = ''
    series_key: str           = ''
    key_type:   str           = 'name'

    def __repr__(self):
        return f"Conference(id={self.conf_id}, key='{self.series_key}', year={self.year})"


@dataclass
class ConferenceEdition:
    # Конкретный выпуск серии (УБС 2023, Воронеж)
    conf_id:      int
    conf_name:    str
    year:         Optional[int]    = None
    location:     Optional[str]    = None
    is_container: bool             = False
    children:     List             = field(default_factory=list)

    @property
    def children_count(self): return len(self.children)

    def to_dict(self):
        d = {'conf_id': self.conf_id, 'conf_name': self.conf_name,
             'year': self.year, 'location': self.location,
             'is_container': self.is_container}
        if self.children:
            d['children'] = [{'conf_id': c.conf_id, 'conf_name': c.conf_name,
                               'year': c.year, 'location': c.location}
                              for c in self.children]
        return d


@dataclass
class ConferenceSeries:
    base_name:  str
    key_type:   str  = 'name'
    confidence: str  = 'high'  # high | medium | low
    editions:   List = field(default_factory=list)

    @property
    def count(self): return len(self.editions)

    @property
    def years(self): return sorted(e.year for e in self.editions if e.year is not None)

    @property
    def year_range(self):
        y = self.years
        if not y: return None
        return str(y[0]) if len(y) == 1 else f'{y[0]}–{y[-1]}'

    @property
    def total_children(self):
        return sum(e.children_count for e in self.editions)

    def display_name(self):
        c = [e.conf_name for e in self.editions if e.conf_name]
        return max(c, key=len) if c else self.base_name

    def to_dict(self):
        return {
            'series_key':     self.base_name,
            'key_type':       self.key_type,
            'confidence':     self.confidence,
            'editions_count': self.count,
            'year_range':     self.year_range,
            'editions': [e.to_dict()
                         for e in sorted(self.editions, key=lambda x: x.year or 0, reverse=True)],
        }

    def __repr__(self):
        return (f"ConferenceSeries(key='{self.base_name}', type='{self.key_type}', "
                f"conf='{self.confidence}', editions={self.count}, years={self.year_range})")