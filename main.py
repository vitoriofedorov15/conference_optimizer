import argparse, json, logging, sys
from csv_loader import load_conferences_from_csv, get_csv_stats
from normalizer import normalize, normalize_batch
from grouper import build_conferences_from_raw, group_conferences, sort_series
from models import Conference, ConferenceSeries

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def print_series(series_list, limit=None, verbose=False):
    shown = series_list[:limit] if limit else series_list
    total = len(series_list)
    print(f"\n{'='*62}\n  Найдено серий конференций: {total}\n{'='*62}")
    for i, s in enumerate(shown, 1):
        yr   = s.year_range or "год неизвестен"
        conf = f"[{s.confidence}]"
        print(f"\n{i:>3}. {s.base_name}  [{s.key_type}] {conf}")
        print(f"      Выпусков: {s.count}  |  Годы: {yr}")
        if s.total_children:
            print(f"      Дочерних конференций: {s.total_children}")
        if verbose:
            for ed in sorted(s.editions, key=lambda x: x.year or 0, reverse=True):
                cont = " [контейнер]" if ed.is_container else ""
                yr_s = str(ed.year) if ed.year else "—"
                loc  = f", {ed.location}" if ed.location else ""
                print(f"        [{yr_s}{loc}] id={ed.conf_id}{cont}")
                for ch in ed.children:
                    print(f"           └─ id={ch.conf_id}  {ch.conf_name[:55]}")
    if limit and total > limit:
        print(f"\n  ... и ещё {total-limit} серий (--limit 0 для вывода всех)")


def print_legacy(conferences):
    print(f"\n{'='*62}\n  Режим «как сейчас»: {len(conferences)} конференций\n{'='*62}")
    for c in conferences[:50]:
        print(f"  id={c.conf_id:>6}  {c.conf_name[:70]}")
    if len(conferences) > 50:
        print(f"  ... и ещё {len(conferences)-50} записей")


def print_stats_block(source, conferences, series_map):
    single = sum(1 for s in series_map.values() if s.count == 1)
    multi  = len(series_map) - single
    print(f"\n{'='*62}\n  СТАТИСТИКА ГРУППИРОВКИ\n{'='*62}")
    print(f"  Источник данных          : {source}")
    print(f"  Конференций загружено    : {len(conferences)}")
    print(f"  Серий итого              : {len(series_map)}")
    print(f"    - многовыпускных       : {multi}")
    print(f"    - одиночных            : {single}")
    if len(conferences) > 0:
        print(f"  Сокращение записей       : {(1-len(series_map)/len(conferences))*100:.1f}%")


def export_results(series_list, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"total_series": len(series_list),
                   "series": [s.to_dict() for s in series_list]},
                  f, ensure_ascii=False, indent=2)


def run_normalize_demo(args):
    examples = [
        "УБС-2023", "УБС-2024 (Красноярск)",
        "Всероссийская школа-конференция «Управление большими системами» (УБС, Воронеж)",
        "MLSD'2019", "DCCN 2022, Moscow",
        "XVII Всероссийское совещание по проблемам управления (ВСПУ-2023)",
        "Мультиконференция по проблемам управления (МКПУ): конференция «УАКС»",
        "Локальная конф. (УРСС, Волгоград), проводимая в рамках МКПУ",
        "Международный симпозиум «Рефлексивные процессы и управление» (Москва)",
        "научно-практическая конференция «Инжиниринг предприятий» (Москва)",
        "Российская конференция «Инжиниринг предприятий» (Москва)",
        "Конференция «Квантовые вычисления» (КВУП, Новосибирск)",
        "STAB 2021", "Управление большими системами",
    ]
    print(f"\n{'='*95}\n  ДЕМОНСТРАЦИЯ АЛГОРИТМА НОРМАЛИЗАЦИИ\n{'='*95}")
    print(f"{'Исходное название':<47} {'Ключ серии':<12} {'База':<20} {'Год':>5}  Локация")
    print("-" * 110)
    for ex in examples:
        r  = normalize(ex)
        kt = r['key_type']
        kd = r['series_key'][:11] if kt == 'abbr' else f"~{r['series_key'][:10]}"
        print(f"{ex[:47]:<47} {kd:<12} {r['base_name'][:20]:<20} "
              f"{str(r['year'] or '—'):>5}  {r['location'] or '—'}")
    print("\nЛегенда: без ~ = аббревиатура (точный),  ~ = по названию (нечёткий)")


def run_csv_mode(args):
    logger.info("Загрузка данных из CSV...")
    raw = load_conferences_from_csv(args.csv)
    if not raw:
        logger.error("Не удалось загрузить данные из CSV.")
        sys.exit(1)
    logger.info(f"Загружено уникальных конференций: {len(raw)}")
    conferences = build_conferences_from_raw(raw)
    if args.legacy:
        print_legacy(conferences); return
    logger.info("Группировка конференций в серии...")
    series_map  = group_conferences(conferences, fuzzy=args.fuzzy)
    sorted_list = sort_series(series_map, by=args.sort)
    if not args.quiet:
        lim = None if args.limit == 0 else (args.limit or 20)
        print_series(sorted_list, limit=lim, verbose=args.verbose)
        print_stats_block("CSV", conferences, series_map)
    if args.export:
        export_results(sorted_list, args.export)
        logger.info(f"Результаты сохранены: {args.export}")


def run_api_mode(args):
    from api_client import ISANDApiClient, ISANDApiError
    client = ISANDApiClient()
    logger.info("Проверка доступности API ИСАНД...")
    if not client.is_available():
        logger.warning("API ИСАНД недоступен. Переключаюсь на CSV-режим.")
        run_csv_mode(args); return
    logger.info(f"API доступен. Поиск: «{args.query or '(все)'}»")
    try:
        raw_api = client.search_conferences(name=args.query)
    except ISANDApiError as e:
        logger.error(f"Ошибка API: {e}"); sys.exit(1)
    logger.info(f"Получено записей: {len(raw_api)}")
    raw = [{"conf_id": r.get("conf_isand_id", 0), "conf_name": r.get("conf_name", "")}
           for r in raw_api]
    conferences = build_conferences_from_raw(raw)
    if args.legacy:
        print_legacy(conferences); return
    series_map  = group_conferences(conferences, fuzzy=args.fuzzy)
    sorted_list = sort_series(series_map, by=args.sort)
    if not args.quiet:
        lim = None if args.limit == 0 else (args.limit or 20)
        print_series(sorted_list, limit=lim, verbose=args.verbose)
        print_stats_block("API ИСАНД", conferences, series_map)
    if args.export:
        export_results(sorted_list, args.export)
        logger.info(f"Результаты сохранены: {args.export}")


def main():
    p = argparse.ArgumentParser(description="Оптимизация выдачи конференций ИСАНД",
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="\nПримеры:\n"
                                       "  python main.py --demo-normalize\n"
                                       "  python main.py --source csv --verbose --limit 10\n"
                                       "  python main.py --source api --query управление\n")
    p.add_argument("--source",        choices=["csv","api"], default="csv")
    p.add_argument("--csv",           default=None)
    p.add_argument("--query",         default=None)
    p.add_argument("--sort",          choices=["count","name","latest"], default="count")
    p.add_argument("--limit",         type=int, default=20)
    p.add_argument("--verbose","-v",  action="store_true")
    p.add_argument("--legacy",        action="store_true")
    p.add_argument("--no-fuzzy",      dest="fuzzy", action="store_false", default=True)
    p.add_argument("--export",        default=None, metavar="FILE")
    p.add_argument("--quiet","-q",    action="store_true")
    p.add_argument("--demo-normalize",action="store_true")
    p.add_argument("--stats",         action="store_true")
    args = p.parse_args()

    if args.demo_normalize:
        run_normalize_demo(args); return
    if args.stats:
        s = get_csv_stats(args.csv)
        print(f"\nСтатистика CSV:")
        for k, v in s.items(): print(f"  {k}: {v}")
        return
    if args.source == "csv":  run_csv_mode(args)
    elif args.source == "api": run_api_mode(args)


if __name__ == "__main__":
    main()