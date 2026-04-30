import argparse, json, sys, urllib.request
from urllib.parse import urlencode
from grouper import build_conferences_from_raw, group_conferences, sort_series

API_BASE = "http://193.232.208.28/api/v2.5"


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def show_before(records):
    print(f"\n{'─'*70}")
    print(f"  КАК СЕЙЧАС — API возвращает {len(records)} отдельных записей")
    print(f"{'─'*70}")
    for i, r in enumerate(records, 1):
        pubs = f"  ({r.get('publ_count','')} публ.)" if r.get('publ_count') else ""
        print(f"  {i:>3}. {r.get('conf_name','')[:68]}{pubs}")


def show_after(records):
    raw   = [{"conf_id": r.get("conf_isand_id", 0), "conf_name": r.get("conf_name", "")}
             for r in records]
    confs  = build_conferences_from_raw(raw)
    smap   = group_conferences(confs)
    slist  = sort_series(smap, by="count", reverse=True)
    multi  = [s for s in slist if s.count > 1]
    single = [s for s in slist if s.count == 1]
    reduction = round((1 - len(slist)/len(records))*100) if records else 0

    print(f"\n{'─'*70}")
    print(f"  ПОСЛЕ АЛГОРИТМА — {len(slist)} серий вместо {len(records)} записей  (-{reduction}%)")
    print(f"{'─'*70}")

    if multi:
        print(f"\n  Серии с несколькими выпусками ({len(multi)} шт.):\n")
        for s in multi:
            yr = f"  {s.year_range}" if s.year_range else ""
            print(f"  ● {s.base_name}{yr}  —  {s.count} выпуска(-ов)")
            for ed in sorted(s.editions, key=lambda x: x.year or 0, reverse=True):
                loc  = f", {ed.location}" if ed.location else ""
                yr_s = str(ed.year) if ed.year else ""
                label = f"{yr_s}{loc}".strip(", ")
                name  = ed.conf_name[:60] if ed.conf_name else ""
                line  = f"    • {name}"
                if label:
                    line += f"  [{label}]"
                print(line)
                for ch in ed.children:
                    print(f"        └ {ch.conf_name[:55]}")
            print()

    if single:
        print(f"  Одиночные конференции ({len(single)} шт.):")
        for s in single[:8]:
            print(f"  ○ {s.editions[0].conf_name[:65]}")
        if len(single) > 8:
            print(f"  ... и ещё {len(single)-8}")

    return slist


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--query", "-q", default="управление")
    p.add_argument("--export", default=None, metavar="FILE")
    args = p.parse_args()

    print(f"\n{'='*70}")
    print(f"  Запрос: «{args.query}»")
    print(f"  URL: {API_BASE}/conferences/search?name={args.query}")
    print(f"{'='*70}")
    print("  Обращаемся к API ИСАНД...", end="", flush=True)

    data = fetch(f"{API_BASE}/conferences/search?" + urlencode({"name": args.query}))
    if not data:
        print(f"\n  Нет данных или API недоступен.")
        sys.exit(1)

    print(f" получено {len(data)} записей.")
    show_before(data)
    series = show_after(data)

    if args.export and series:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump({"query": args.query, "raw_count": len(data),
                       "series_count": len(series),
                       "series": [s.to_dict() for s in series]},
                      f, ensure_ascii=False, indent=2)
        print(f"\n  Сохранено: {args.export}")
    print()


if __name__ == "__main__":
    main()