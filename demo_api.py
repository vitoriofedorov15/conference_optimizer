"""
Живая демонстрация на реальных данных API ИСАНД.

Запуск:
    python demo_api.py
    python demo_api.py --query мкпу
    python demo_api.py --query убс
    python demo_api.py --query dccn
    python demo_api.py --query управление

Показывает:
    1. Что сейчас возвращает API (сырой список с дублями)
    2. Что возвращает алгоритм (сгруппированные серии)
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

from grouper import build_conferences_from_raw, group_conferences, sort_series

API_BASE = "http://193.232.208.28/api/v2.5"


def fetch(query: str):
    """Делает реальный запрос к API ИСАНД и возвращает список конференций."""
    from urllib.parse import urlencode
    url = f"{API_BASE}/conferences/search?" + urlencode({"name": query})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, list):
                return data
            return []
    except Exception as e:
        print(f"\n  [!] Не удалось подключиться к API: {e}")
        print(f"      URL: {url}")
        return []


def show_before(records: list):
    """Выводит сырой ответ API — как видит пользователь сейчас."""
    print(f"\n{'─'*70}")
    print(f"  КАК СЕЙЧАС — API возвращает {len(records)} отдельных записей")
    print(f"{'─'*70}")
    for i, r in enumerate(records, 1):
        cid  = r.get("conf_isand_id", "?")
        name = r.get("conf_name", "")
        pubs = r.get("publ_count", "")
        pubs_str = f"  ({pubs} публ.)" if pubs else ""
        print(f"  {i:>3}. [id={cid}] {name[:65]}{pubs_str}")


def show_after(records: list):
    """Прогоняет через алгоритм и выводит сгруппированные серии."""
    raw = [
        {"conf_id": r.get("conf_isand_id", 0), "conf_name": r.get("conf_name", "")}
        for r in records
    ]
    confs      = build_conferences_from_raw(raw)
    series_map = group_conferences(confs)
    sorted_s   = sort_series(series_map, by="count", reverse=True)

    multi  = [s for s in sorted_s if s.count > 1]
    single = [s for s in sorted_s if s.count == 1]

    reduction = round((1 - len(sorted_s) / len(records)) * 100) if records else 0

    print(f"\n{'─'*70}")
    print(f"  ПОСЛЕ АЛГОРИТМА — {len(sorted_s)} серий вместо {len(records)} записей  "
          f"(-{reduction}% записей)")
    print(f"{'─'*70}")

    if multi:
        print(f"\n  Серии с несколькими выпусками ({len(multi)} шт.):")
        for s in multi:
            yr    = s.year_range or "?"
            ktype = "abbr" if s.key_type == "abbr" else "title"
            print(f"\n    [{s.count} вып.] {s.base_name}  [{ktype}]  годы: {yr}")
            for ed in sorted(s.editions, key=lambda x: x.year or 0, reverse=True):
                loc    = f", {ed.location}" if ed.location else ""
                yr_str = str(ed.year) if ed.year else "—"
                name60 = ed.conf_name[:60] + ("…" if len(ed.conf_name) > 60 else "")
                print(f"         [{yr_str}{loc}] id={ed.conf_id}  «{name60}»")

    if single:
        print(f"\n  Одиночные конференции ({len(single)} шт.) — без дублей, отдельные серии:")
        for s in single[:10]:
            ed   = s.editions[0]
            name = ed.conf_name[:55] + ("…" if len(ed.conf_name) > 55 else "")
            print(f"    id={ed.conf_id}  «{name}»")
        if len(single) > 10:
            print(f"    ... и ещё {len(single) - 10}")

    return sorted_s


def main():
    parser = argparse.ArgumentParser(
        description="Живая демонстрация группировки конференций ИСАНД",
    )
    parser.add_argument(
        "--query", "-q", default="управление",
        help="Поисковый запрос (по умолчанию: управление)",
    )
    parser.add_argument(
        "--export", default=None, metavar="FILE",
        help="Сохранить результат в JSON",
    )
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  ДЕМОНСТРАЦИЯ: запрос «{args.query}»")
    print(f"  API: {API_BASE}/conferences/search?name={args.query}")
    print(f"{'='*70}")

    print("\n  Обращаемся к API ИСАНД...", end="", flush=True)
    records = fetch(args.query)

    if not records:
        print("\n  Данных нет или API недоступен.")
        print(f"\n  Попробуй открыть в браузере:")
        print(f"  {API_BASE}/conferences/search?name={args.query}")
        sys.exit(1)

    print(f" получено {len(records)} записей.")

    show_before(records)
    series = show_after(records)

    if args.export and series:
        data = {
            "query":        args.query,
            "raw_count":    len(records),
            "series_count": len(series),
            "series": [s.to_dict() for s in series],
        }
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n  Результат сохранён: {args.export}")

    print()


if __name__ == "__main__":
    main()
