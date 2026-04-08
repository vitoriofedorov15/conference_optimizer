"""
Загрузчик тестовых данных из CSV-файла.

CSV содержит строки вида:
    conference_id, conference_name, publication_id,
    publication_title, publication_date, doi

Модуль извлекает уникальные конференции и статистику по публикациям.
"""

import csv
from collections import defaultdict
from typing import List, Dict, Optional
from pathlib import Path


DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "conferences_with_publications.csv"


def load_conferences_from_csv(path: str = None) -> List[Dict]:
    """
    Загружает уникальные конференции из CSV и возвращает список словарей.

    Возвращает список уникальных конференций с агрегированной статистикой:
        conf_id, conf_name, publications_count, years (set)

    Parameters
    ----------
    path : str, optional
        Путь к CSV-файлу. По умолчанию data/conferences_with_publications.csv

    Returns
    -------
    list of dict
    """
    filepath = Path(path) if path else DEFAULT_CSV_PATH

    if not filepath.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {filepath}")

    # Агрегируем данные по конференциям
    conf_data: Dict[str, Dict] = {}
    errors = 0

    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                conf_id = row.get("conference_id", "").strip()
                conf_name = row.get("conference_name", "").strip()

                if not conf_id or conf_id == "(21814 строк)" or conf_name == "None":
                    continue

                if conf_id not in conf_data:
                    conf_data[conf_id] = {
                        "conf_id": conf_id,
                        "conf_name": conf_name,
                        "publications_count": 0,
                        "years": set(),
                    }

                # Считаем публикации
                pub_id = row.get("publication_id", "").strip()
                if pub_id:
                    conf_data[conf_id]["publications_count"] += 1

                # Собираем годы публикаций
                pub_date = row.get("publication_date", "").strip()
                if pub_date and len(pub_date) >= 4:
                    try:
                        year = int(pub_date[:4])
                        if 1900 <= year <= 2099:
                            conf_data[conf_id]["years"].add(year)
                    except ValueError:
                        pass

            except Exception:
                errors += 1
                continue

    if errors:
        print(f"[csv_loader] Пропущено строк с ошибками: {errors}")

    # Преобразуем set годов в отсортированный список
    result = []
    for item in conf_data.values():
        item["years"] = sorted(item["years"])
        result.append(item)

    return result


def load_raw_publications(path: str = None) -> List[Dict]:
    """
    Загружает все строки CSV как публикации (без агрегации).

    Returns
    -------
    list of dict с полями: conference_id, conference_name,
        publication_id, publication_title, publication_date, doi
    """
    filepath = Path(path) if path else DEFAULT_CSV_PATH

    if not filepath.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {filepath}")

    result = []
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conf_id = row.get("conference_id", "").strip()
            if not conf_id or conf_id == "(21814 строк)":
                continue
            result.append({
                "conference_id": conf_id,
                "conference_name": row.get("conference_name", "").strip(),
                "publication_id": row.get("publication_id", "").strip(),
                "publication_title": row.get("publication_title", "").strip(),
                "publication_date": row.get("publication_date", "").strip(),
                "doi": row.get("doi", "").strip(),
            })
    return result


def get_csv_stats(path: str = None) -> Dict:
    """Возвращает базовую статистику по CSV-файлу."""
    conferences = load_conferences_from_csv(path)
    publications = load_raw_publications(path)

    unique_names = set(c["conf_name"] for c in conferences)

    return {
        "total_rows": len(publications),
        "unique_conferences": len(conferences),
        "unique_conference_names": len(unique_names),
        "conference_names": sorted(unique_names),
    }
