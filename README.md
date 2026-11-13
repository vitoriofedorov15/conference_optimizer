# Conference Optimizer

**Turn scattered conference records into browsable event series.**

Conference editions often appear as separate records with different years, locations and spellings. This Python module groups related records into series while preserving edition IDs, names, dates and nested events. The result is structured JSON ready for a catalogue, search interface or further analysis.

**[Try the local CSV example →](examples/conferences.csv)** · [See the grouped result](examples/grouped.json)

## From records to series

Synthetic input:

```csv
conference_id,conference_name
101,ALC-2023
102,ALC-2024
103,Мультиконференция (ALC): секция «Данные» 2024
```

These records produce one `ALC` series with two editions. Record `103` remains accessible as a child of the 2024 edition. The complete six-record demo produces three series: `ALC`, `QDS` and `NEO`.

Actual output excerpt from the demo:

```json
{
  "series_key": "ALC",
  "key_type": "abbr",
  "confidence": "high",
  "editions_count": 2,
  "year_range": "2023–2024",
  "editions": [
    {
      "conf_id": 102,
      "conf_name": "ALC-2024",
      "year": 2024,
      "location": null,
      "is_container": true,
      "children": [
        {
          "conf_id": 103,
          "conf_name": "Мультиконференция (ALC): секция «Данные» 2024",
          "year": 2024,
          "location": null
        }
      ]
    },
    {
      "conf_id": 101,
      "conf_name": "ALC-2023",
      "year": 2023,
      "location": null,
      "is_container": false
    }
  ]
}
```

## Quick start

Python 3.10+. The CSV pipeline and standard-library tests work without installing dependencies or contacting an API.

```bash
git clone https://github.com/vitoriofedorov15/conference_optimizer.git
cd conference_optimizer
python3 main.py --source csv --csv examples/conferences.csv --verbose --limit 0 --export examples/grouped.json
```

Open [`examples/grouped.json`](examples/grouped.json) to inspect the series and their editions. The existing CLI prints Russian status messages; JSON uses English field names and preserves original event names.

## What it does

- Extracts years, locations and a stable grouping key from event names.
- Matches explicit acronyms and normalized titles.
- Uses Levenshtein similarity for approximate title matching.
- Retains individual editions and attaches nested events to a parent series.
- Exports sorted series with IDs, year ranges and grouping confidence labels.

Confidence labels describe the rule used (`high` for an acronym, `medium` for a title, `low` for approximate matching); they are not statistical probabilities.

## Use your own CSV

Required columns: `conference_id`, `conference_name`. Optional publication fields are supported by the loader: `publication_id`, `publication_title`, `publication_date`, `doi`. Repeated conference IDs are collapsed by the loader before grouping.

```bash
python3 main.py --source csv --csv path/to/records.csv --sort latest --export result.json
```

| Option | Purpose |
|---|---|
| `--verbose` | Show editions and nested events |
| `--sort count`, `name`, `latest` | Choose series ordering |
| `--limit 0` | Show all series |
| `--quiet` | Export without the main presentation tables |
| `--legacy` | Inspect ungrouped records |
| `--demo-normalize` | Inspect normalization examples |

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 examples/evaluate.py
```

The existing suite contains **90 passing tests** covering normalization, grouping, nested events, models and sorting. The additional script checks **24 synthetic labeled pairs** at three similarity thresholds. Its fixtures include editions, spelling variants, nested events and similarly named separate series. The script prints its results locally.

[`examples/labeled_pairs.csv`](examples/labeled_pairs.csv) records the expected relationship and a rationale for each pair. These small, deliberately authored examples are intended for development and reproduction.

## Python API

```python
from grouper import build_conferences_from_raw, group_conferences, sort_series

records = [
    {"conf_id": 101, "conf_name": "ALC-2023"},
    {"conf_id": 102, "conf_name": "ALC-2024"},
]
conferences = build_conferences_from_raw(records)
series = group_conferences(conferences, fuzzy_threshold=0.9)
output = [item.to_dict() for item in sort_series(series)]
```

## Structure

```text
normalizer.py       Name, year and location normalization
series_key.py       Acronym and title key extraction
grouper.py          Exact/fuzzy grouping and parent-child handling
models.py           Records, editions and series
csv_loader.py       Local CSV input
main.py             CLI and JSON export
api_client.py       Optional external data adapter
db_schema.sql       SQL schema for series and editions
examples/           Synthetic demo, expected pairs and evaluator
tests/              Standard-library test suite
```

The optional external API adapter requires the packages in `requirements.txt`. The quick start uses only local data. Original project data is retained in `data/`; the public demo and evaluation fixtures are newly authored synthetic records. They contain no personal information and may be reused freely (CC0-1.0 for files in `examples/`).
