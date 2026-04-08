"""
Модуль группировки конференций в серии.

После нормализации конференции объединяются в серии по ключу series_key.
Fuzzy-matching применяется только к ключам типа 'title' и 'name'
(аббревиатуры сравниваются точно — они уже стандартизованы).

Алгоритм работает с любыми конференциями — без хардкода названий.
"""

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from models import Conference, ConferenceSeries
from normalizer import normalize


# ── Расстояние Левенштейна ────────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[len(b)]


def _similarity(a: str, b: str) -> float:
    ml = max(len(a), len(b))
    if ml == 0: return 1.0
    return 1.0 - _levenshtein(a, b) / ml


# ── Построение конференций из сырых данных ────────────────────────────────────

def build_conferences_from_raw(raw_list: list) -> List[Conference]:
    """
    Принимает список dict с полями conf_id и conf_name (формат API ИСАНД),
    применяет нормализацию, возвращает список Conference.

    Параметры
    ----------
    raw_list : list of dict
        Каждый dict содержит:
          - conf_id   : идентификатор в ИСАНД (int или str)
          - conf_name : полное название конференции

    Возвращает
    ----------
    list of Conference
    """
    result = []
    for item in raw_list:
        raw_id   = item.get('conf_id') or item.get('conf_isand_id') or 0
        raw_name = item.get('conf_name') or ''
        try:
            conf_id = int(raw_id)
        except (ValueError, TypeError):
            conf_id = 0

        norm = normalize(raw_name)
        conf = Conference(
            conf_id    = conf_id,
            conf_name  = raw_name,
            year       = norm['year'],
            location   = norm['location'],
            base_name  = norm['base_name'],
            series_key = norm['series_key'],
            key_type   = norm['key_type'],
        )
        result.append(conf)
    return result


# ── Основная группировка ──────────────────────────────────────────────────────

def group_conferences(
    conferences: List[Conference],
    fuzzy: bool = True,
    fuzzy_threshold: float = 0.88,
) -> Dict[str, ConferenceSeries]:
    """
    Группирует список конференций в серии по ключу series_key.

    Логика:
    - Ключи типа 'abbr' сравниваются ТОЧНО (аббревиатуры стандартизованы).
    - Ключи типа 'title'/'name' при fuzzy=True сравниваются нечётко
      (расстояние Левенштейна), что позволяет объединять варианты с
      незначительными орфографическими различиями.

    Параметры
    ----------
    conferences    : список Conference
    fuzzy          : включить нечёткое сравнение для title/name ключей
    fuzzy_threshold: порог схожести [0, 1] (по умолчанию 0.88)

    Возвращает
    ----------
    dict: series_key -> ConferenceSeries
    """
    # Разделяем на abbr-ключи (точные) и title/name ключи (fuzzy)
    abbr_map:  Dict[str, ConferenceSeries] = {}
    fuzzy_map: Dict[str, ConferenceSeries] = {}  # для title/name

    for conf in conferences:
        key   = conf.series_key
        ktype = conf.key_type

        if not key:
            key   = f'[без названия #{conf.conf_id}]'
            ktype = 'name'

        if ktype == 'abbr':
            # Точное совпадение
            if key not in abbr_map:
                abbr_map[key] = ConferenceSeries(
                    base_name  = key,
                    key_type   = 'abbr',
                )
            abbr_map[key].editions.append(conf)

        else:
            # Fuzzy-matching для title/name
            if fuzzy:
                best_key = _find_fuzzy_key(key, fuzzy_map, fuzzy_threshold)
            else:
                best_key = key if key in fuzzy_map else None

            if best_key:
                fuzzy_map[best_key].editions.append(conf)
            else:
                fuzzy_map[key] = ConferenceSeries(
                    base_name = key,
                    key_type  = ktype,
                )
                fuzzy_map[key].editions.append(conf)

    # Объединяем результаты
    result = {}
    result.update(abbr_map)
    result.update(fuzzy_map)
    return result


def _find_fuzzy_key(
    key: str,
    existing: Dict[str, ConferenceSeries],
    threshold: float,
) -> Optional[str]:
    """Ищет похожий ключ среди уже существующих серий."""
    best_key   = None
    best_score = 0.0
    for k in existing:
        score = _similarity(key, k)
        if score >= threshold and score > best_score:
            best_score = score
            best_key   = k
    return best_key


# ── Сортировка результатов ────────────────────────────────────────────────────

def sort_series(
    series_map: Dict[str, ConferenceSeries],
    by: str = 'count',
    reverse: bool = True,
) -> List[ConferenceSeries]:
    """
    Сортирует серии конференций.

    Параметры
    ----------
    by      : 'count' | 'name' | 'latest'
    reverse : обратный порядок

    Возвращает
    ----------
    list of ConferenceSeries
    """
    key_fns = {
        'count':  lambda s: s.count,
        'name':   lambda s: s.base_name.lower(),
        'latest': lambda s: max(s.years) if s.years else 0,
    }
    fn = key_fns.get(by, key_fns['count'])
    return sorted(series_map.values(), key=fn, reverse=reverse)
