"""
Оптимизация выдачи конференций — главный модуль.

Использование:
    python main.py --demo-normalize
    python main.py --source csv
    python main.py --source csv --limit 10 --verbose
    python main.py --source csv --legacy
    python main.py --source csv --export result.json
    python main.py --source api --query управление
    python main.py --stats
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from csv_loader import load_conferences_from_csv, get_csv_stats
from normalizer import normalize, normalize_batch
from grouper import build_conferences_from_raw, group_conferences, sort_series
from models import Conference, ConferenceSeries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Вывод результатов ─────────────────────────────────────────────────────────

def print_series(series_list: list, limit=None, verbose: bool = False):
    shown = series_list[:limit] if limit else series_list
    total = len(series_list)

    print(f"\n{'='*62}")
    print(f"  Найдено серий конференций: {total}")
    print(f"{'='*62}")

    for i, s in enumerate(shown, 1):
        yr    = s.year_range or "год неизвестен"
        ktype = f"[{s.key_type}]"
        print(f"\n{i:>3}. {s.base_name}  {ktype}")
        print(f"      Выпусков: {s.count}  |  Годы: {yr}")
        if verbose:
            for ed in sorted(s.editions, key=lambda x: x.year or 0, reverse=True):
                loc    = f", {ed.location}" if ed.location else ""
                yr_str = str(ed.year) if ed.year else "—"
                print(f"           [{yr_str}{loc}] id={ed.conf_id}  «{ed.conf_name[:60]}»")

    if limit and total > limit:
        print(f"\n  ... и ещё {total - limit} серий (используйте --limit 0 для вывода всех)")


def print_legacy(conferences: list):
    print(f"\n{'='*62}")
    print(f"  Режим «как сейчас»: {len(conferences)} конференций")
    print(f"{'='*62}")
    for c in conferences[:50]:
        print(f"  id={c.conf_id:>6}  {c.conf_name[:70]}")
    if len(conferences) > 50:
        print(f"  ... и ещё {len(conferences) - 50} записей")


def print_stats_block(source: str, conferences: list, series_map: dict):
    single = sum(1 for s in series_map.values() if s.count == 1)
    multi  = len(series_map) - single

    print(f"\n{'='*62}")
    print(f"  СТАТИСТИКА ГРУППИРОВКИ")
    print(f"{'='*62}")
    print(f"  Источник данных          : {source}")
    print(f"  Конференций загружено    : {len(conferences)}")
    print(f"  Серий итого              : {len(series_map)}")
    print(f"    - многовыпускных       : {multi}")
    print(f"    - одиночных            : {single}")
    if len(conferences) > 0:
        reduction = (1 - len(series_map) / len(conferences)) * 100
        print(f"  Сокращение записей       : {reduction:.1f}%")


# ── Режимы работы ─────────────────────────────────────────────────────────────

def run_csv_mode(args):
    logger.info("Загрузка данных из CSV...")
    raw = load_conferences_from_csv(args.csv)
    if not raw:
        logger.error("Не удалось загрузить данные из CSV.")
        sys.exit(1)
    logger.info(f"Загружено уникальных конференций: {len(raw)}")

    conferences = build_conferences_from_raw(raw)

    if args.legacy:
        print_legacy(conferences)
        return

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
        run_csv_mode(args)
        return

    logger.info(f"API доступен. Поиск по запросу: «{args.query or '(все)'}»")
    try:
        raw_api = client.search_conferences(name=args.query)
    except ISANDApiError as e:
        logger.error(f"Ошибка API: {e}")
        sys.exit(1)

    logger.info(f"Получено записей: {len(raw_api)}")

    raw = [
        {
            "conf_id":   item.get("conf_isand_id", 0),
            "conf_name": item.get("conf_name", ""),
        }
        for item in raw_api
    ]

    conferences = build_conferences_from_raw(raw)

    if args.legacy:
        print_legacy(conferences)
        return

    series_map  = group_conferences(conferences, fuzzy=args.fuzzy)
    sorted_list = sort_series(series_map, by=args.sort)

    if not args.quiet:
        lim = None if args.limit == 0 else (args.limit or 20)
        print_series(sorted_list, limit=lim, verbose=args.verbose)
        print_stats_block("API ИСАНД", conferences, series_map)

    if args.export:
        export_results(sorted_list, args.export)
        logger.info(f"Результаты сохранены: {args.export}")


def run_normalize_demo(args):
    """Демонстрация алгоритма нормализации на примерах."""
    examples = [
        "УБС-2023",
        "УБС-2024 (Красноярск)",
        "Всероссийская школа-конференция «Управление большими системами» (УБС, Воронеж)",
        "MLSD'2019",
        "DCCN 2022, Moscow",
        "XVII Всероссийское совещание по проблемам управления (ВСПУ-2023)",
        "Мультиконференция по проблемам управления (МКПУ): конференция «УАКС»",
        "Локальная конф. (УРСС, Волгоград), проводимая в рамках МКПУ",
        "Международный симпозиум «Рефлексивные процессы и управление» (Москва)",
        "научно-практическая конференция «Инжиниринг предприятий» (Москва)",
        "Российская конференция «Инжиниринг предприятий» (Москва)",
        "Конференция «Квантовые вычисления» (КВУП, Новосибирск)",
        "STAB 2021",
        "Управление большими системами",
    ]

    print(f"\n{'='*90}")
    print("  ДЕМОНСТРАЦИЯ АЛГОРИТМА НОРМАЛИЗАЦИИ")
    print(f"{'='*90}")
    print(f"{'Исходное название':<47} {'Ключ серии':<12} {'База':<20} {'Год':>5}  Локация")
    print("-" * 110)

    for ex in examples:
        r    = normalize(ex)
        base = r['base_name']
        year = r['year']
        loc  = r['location']
        key  = r['series_key']
        kt   = r['key_type']

        key_display = f"{key[:11]}" if kt == 'abbr' else f"~{key[:10]}"
        print(f"{ex[:47]:<47} {key_display:<12} {base[:20]:<20} {str(year or '—'):>5}  {loc or '—'}")

    print()
    print("Легенда ключей: без ~ = аббревиатура (точный),  ~ = по названию (нечёткий)")


def export_results(series_list: list, filepath: str):
    data = {
        "total_series": len(series_list),
        "series": [s.to_dict() for s in series_list],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="Оптимизация выдачи конференций в ИСАНД",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python main.py --demo-normalize
  python main.py --source csv
  python main.py --source csv --verbose --limit 10
  python main.py --source csv --legacy
  python main.py --source csv --export output.json
  python main.py --source api --query управление
  python main.py --stats
        """,
    )
    parser.add_argument("--source", choices=["csv", "api"], default="csv",
                        help="Источник данных (по умолчанию: csv)")
    parser.add_argument("--csv", default=None,
                        help="Путь к CSV-файлу")
    parser.add_argument("--query", default=None,
                        help="Поисковый запрос для API")
    parser.add_argument("--sort", choices=["count", "name", "latest"], default="count",
                        help="Сортировка серий")
    parser.add_argument("--limit", type=int, default=20,
                        help="Максимум серий для вывода (0 = все)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Подробный вывод: показывать каждый выпуск")
    parser.add_argument("--legacy", action="store_true",
                        help="Режим «как сейчас»: без группировки")
    parser.add_argument("--no-fuzzy", dest="fuzzy", action="store_false", default=True,
                        help="Отключить нечёткое сравнение названий")
    parser.add_argument("--export", default=None, metavar="FILE",
                        help="Сохранить результаты в JSON")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Не выводить на экран")
    parser.add_argument("--demo-normalize", action="store_true",
                        help="Показать демонстрацию алгоритма нормализации")
    parser.add_argument("--stats", action="store_true",
                        help="Показать статистику по CSV-файлу")
    return parser


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.demo_normalize:
        run_normalize_demo(args)
        return

    if args.stats:
        stats = get_csv_stats(args.csv)
        print(f"\nСтатистика CSV-файла:")
        print(f"  Строк всего         : {stats['total_rows']}")
        print(f"  Уникальных конф-й   : {stats['unique_conferences']}")
        print(f"  Уникальных названий : {stats['unique_conference_names']}")
        print(f"  Названия            : {', '.join(stats['conference_names'])}")
        return

    if args.source == "csv":
        run_csv_mode(args)
    elif args.source == "api":
        run_api_mode(args)


if __name__ == "__main__":
    main()