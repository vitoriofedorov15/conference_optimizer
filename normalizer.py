"""
Модуль нормализации названий конференций.

Для каждого названия конференции извлекает:
  - base_name  : базовое название серии (без года, локации, служебных слов)
  - year       : год проведения (int или None)
  - location   : место проведения (str или None)
  - series_key : ключ серии — используется для группировки

Алгоритм полностью универсален: не содержит хардкода конкретных
аббревиатур или названий конференций.
"""

import re
from typing import Optional, Tuple
from series_key import get_series_key

# ── Паттерны извлечения года ──────────────────────────────────────────────────

_YEAR_PATTERNS = [
    # год через дефис/апостроф в конце: УБС-2023, MLSD'2019
    re.compile(r"[-'–]\s*(\d{4})\s*$"),
    # год в скобках: (2024), (Москва, 2024), (2024, Москва)
    re.compile(r'\(\s*(?:[^),]*,\s*)?(\d{4})\s*(?:,\s*[^)]*)?\)'),
    re.compile(r'\(\s*(\d{4})\s*\)'),
    # год перед запятой+место: DCCN 2022, Moscow
    re.compile(r'\s(\d{4})\s*,'),
    # год после запятой в конце: конференция, 2022
    re.compile(r',\s*(\d{4})\s*$'),
    # год через пробел в конце: STAB 2021
    re.compile(r'\s(\d{4})\s*$'),
    # год в аббревиатуре в скобках: (ВСПУ-2023)
    re.compile(r'\([А-ЯЁA-Z]{2,8}-(\d{4})\)'),
]

# ── Паттерны извлечения локации ───────────────────────────────────────────────

_LOCATION_PATTERNS = [
    # (Город, год) или (год, Город)
    re.compile(
        r'\(\s*([А-ЯЁA-Za-z][А-ЯЁA-Za-zа-яё\s\-\.]+?)'
        r'(?:\s*-\s*[А-ЯЁA-Za-zа-яё\s\-\.]+?)?'   # двойные города: Санкт-Петербург-Судак
        r'(?:\s*,\s*(?:[А-ЯЁA-Za-zа-яё]+\s*,\s*)?\d{4})?\s*\)'
    ),
    re.compile(r'\(\s*\d{4}\s*,\s*([А-ЯЁA-Za-z][А-ЯЁA-Za-zа-яё\s\-\.]+?)\s*\)'),
    # город после запятой в конце: ..., Москва или ..., Moscow
    re.compile(r',\s*([А-ЯЁA-Za-z][А-ЯЁA-Za-zа-яё\s\-\.]{2,})\s*$'),
]

# Слова которые не являются локацией (аббревиатуры конференций)
_NOT_LOCATION = re.compile(r'^[А-ЯЁA-Z]{2,8}(?:-\d+)?$')

# ── Слова для очистки базового названия ──────────────────────────────────────

_TRAILING_NOISE = re.compile(r'\s*[,;:\-–—]\s*$')


def _extract_year(text: str) -> Optional[int]:
    """Ищет год (1900–2099) в строке по набору паттернов."""
    for pat in _YEAR_PATTERNS:
        m = pat.search(text)
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2099:
                return y
    return None


def _extract_location(text: str) -> Optional[str]:
    """
    Ищет место проведения конференции.
    Возвращает строку или None.
    """
    for pat in _LOCATION_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        loc = m.group(1).strip()
        # Фильтры: длина, не аббревиатура конференции, не год
        if len(loc) < 2 or len(loc) > 60:
            continue
        if _NOT_LOCATION.match(loc):
            continue
        if re.match(r'^\d+$', loc):
            continue
        return loc
    return None


def _build_base_name(text: str, year: Optional[int]) -> str:
    """
    Строит базовое название: убирает скобочные блоки с годом/локацией,
    удаляет год в явном виде, чистит хвостовые разделители.
    """
    base = text

    # Удаляем скобочные блоки содержащие год
    if year:
        base = re.sub(rf'\([^)]*{year}[^)]*\)', '', base)
        base = re.sub(rf'\[[^\]]*{year}[^\]]*\]', '', base)
        # Удаляем год с разделителем: -2023, '2023, , 2023, пробел2023
        base = re.sub(rf"[-'–\s,]+{year}\b", '', base)
        base = re.sub(rf'\b{year}[-\u2013\s,]+', '', base)
        base = re.sub(rf'\b{year}\b', '', base)

    # Удаляем пустые скобки
    base = re.sub(r'\(\s*\)', '', base)
    base = re.sub(r'\[\s*\]', '', base)

    # Убираем хвостовые разделители и пробелы
    base = _TRAILING_NOISE.sub('', base.strip())
    base = re.sub(r'\s{2,}', ' ', base).strip()

    return base if base else text.strip()


def normalize(conf_name: str) -> dict:
    """
    Нормализует название конференции.

    Параметры
    ----------
    conf_name : str
        Полное название конференции из API ИСАНД (поле conf_name).

    Возвращает
    ----------
    dict с полями:
        original   : исходное название
        base_name  : базовое название (для отображения)
        year       : год проведения или None
        location   : место проведения или None
        series_key : ключ серии (используется для группировки)
        key_type   : тип ключа ('abbr' | 'title' | 'name')
    """
    if not conf_name or not conf_name.strip():
        return {
            'original': conf_name or '',
            'base_name': '',
            'year': None,
            'location': None,
            'series_key': '',
            'key_type': 'name',
        }

    text = conf_name.strip()
    text = re.sub(r'\s{2,}', ' ', text)

    year     = _extract_year(text)
    location = _extract_location(text)
    base     = _build_base_name(text, year)
    ktype, key = get_series_key(text)

    return {
        'original':   conf_name,
        'base_name':  base,
        'year':       year,
        'location':   location,
        'series_key': key,
        'key_type':   ktype,
    }


def normalize_batch(names: list) -> list:
    """Нормализует список названий конференций."""
    return [normalize(n) for n in names]
