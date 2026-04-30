import re
from typing import Dict, List, Optional
from models import Conference, ConferenceEdition, ConferenceSeries
from normalizer import normalize


def _levenshtein(a, b):
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(0 if ca==cb else 1)))
        prev = curr
    return prev[len(b)]


def _similarity(a, b):
    ml = max(len(a), len(b))
    return 1.0 if ml == 0 else 1.0 - _levenshtein(a, b) / ml


_VRAMKAKH = re.compile(r'в\s+рамках', re.IGNORECASE)


def _is_child(conf_name, key_type):
    # Дочерняя конференция: «в рамках МКПУ» или «Мультиконф (МКПУ): подконф»
    if _VRAMKAKH.search(conf_name): return True
    if ':' in conf_name and key_type == 'abbr':
        before = conf_name.split(':', 1)[0]
        if re.search(r'\([А-ЯЁA-Z]{2,8}[,\s\)]', before): return True
    return False


def build_conferences_from_raw(raw_list):
    result = []
    for item in raw_list:
        raw_id   = item.get('conf_id') or item.get('conf_isand_id') or 0
        raw_name = item.get('conf_name') or ''
        try: conf_id = int(raw_id)
        except: conf_id = 0
        norm = normalize(raw_name)
        # Год из CSV (_year_from_csv) приоритетнее года из названия
        year = item.get('_year_from_csv') or norm['year']
        result.append(Conference(
            conf_id=conf_id, conf_name=raw_name,
            year=year, location=norm['location'],
            base_name=norm['base_name'],
            series_key=norm['series_key'], key_type=norm['key_type'],
        ))
    return result


def group_conferences(conferences, fuzzy=True, fuzzy_threshold=0.9):
    independent, children = [], []
    for conf in conferences:
        (children if _is_child(conf.conf_name, conf.key_type) else independent).append(conf)

    abbr_map, fuzzy_map = {}, {}

    for conf in independent:
        key   = conf.series_key or f'[id:{conf.conf_id}]'
        ktype = conf.key_type

        if ktype == 'abbr':
            if key not in abbr_map:
                abbr_map[key] = ConferenceSeries(base_name=key, key_type='abbr', confidence='high')
            abbr_map[key].editions.append(
                ConferenceEdition(conf_id=conf.conf_id, conf_name=conf.conf_name,
                                  year=conf.year, location=conf.location))
        else:
            best_key, best_sim = None, 0.0
            if fuzzy:
                for k in fuzzy_map:
                    s = _similarity(key, k)
                    if s >= fuzzy_threshold and s > best_sim:
                        best_sim, best_key = s, k
            if best_key:
                series = fuzzy_map[best_key]
                if best_sim < 1.0: series.confidence = 'low'
            else:
                conf_level = 'medium' if ktype == 'title' else 'low'
                fuzzy_map[key] = ConferenceSeries(base_name=key, key_type=ktype,
                                                   confidence=conf_level)
                series = fuzzy_map[key]
            series.editions.append(
                ConferenceEdition(conf_id=conf.conf_id, conf_name=conf.conf_name,
                                  year=conf.year, location=conf.location))

    result = {**abbr_map, **fuzzy_map}

    for child in children:
        key = child.series_key
        if key not in result:
            result[key] = ConferenceSeries(
                base_name=key, key_type=child.key_type,
                confidence='high' if child.key_type == 'abbr' else 'medium')

        series = result[key]
        target = next((e for e in series.editions if e.year == child.year), None)
        if target is None and series.editions:
            target = series.editions[0]
        if target is None:
            target = ConferenceEdition(conf_id=0, conf_name=f'{key} (контейнер)',
                                        year=child.year, location=child.location,
                                        is_container=True)
            series.editions.append(target)

        target.is_container = True
        target.children.append(Conference(
            conf_id=child.conf_id, conf_name=child.conf_name,
            year=child.year, location=child.location,
            series_key=child.series_key, key_type=child.key_type))

    return result


def _find_fuzzy_key(key, existing, threshold):
    best_key, best_score = None, 0.0
    for k in existing:
        score = _similarity(key, k)
        if score >= threshold and score > best_score:
            best_score, best_key = score, k
    return best_key


def sort_series(series_map, by='count', reverse=True):
    fns = {
        'count':  lambda s: s.count,
        'name':   lambda s: s.base_name.lower(),
        'latest': lambda s: max(s.years) if s.years else 0,
    }
    return sorted(series_map.values(), key=fns.get(by, fns['count']), reverse=reverse)