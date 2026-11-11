"""Evaluate isolated labeled pairs through the existing grouping pipeline."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from grouper import build_conferences_from_raw, group_conferences


def evaluate(pairs, threshold):
    counts = dict(tp=0, fp=0, fn=0, tn=0)
    for pair in pairs:
        conferences = build_conferences_from_raw([
            {'conf_id':1,'conf_name':pair['left']},
            {'conf_id':2,'conf_name':pair['right']},
        ])
        groups = group_conferences(conferences, fuzzy_threshold=threshold)
        memberships = []
        for series in groups.values():
            ids = set()
            for edition in series.editions:
                ids.add(edition.conf_id)
                ids.update(child.conf_id for child in edition.children)
            memberships.append(ids)
        predicted = any({1,2} <= ids for ids in memberships)
        expected = pair['expected_same_series'] == '1'
        outcome = ('tp' if expected else 'fp') if predicted else ('fn' if expected else 'tn')
        counts[outcome] += 1
    tp,fp,fn = counts['tp'],counts['fp'],counts['fn']
    return dict(threshold=threshold, **counts,
                precision=round(tp/(tp+fp),3) if tp+fp else None,
                recall=round(tp/(tp+fn),3) if tp+fn else None)


def main():
    with (HERE/'labeled_pairs.csv').open(encoding='utf-8',newline='') as f:
        pairs = list(csv.DictReader(f))
    results = [evaluate(pairs,t) for t in (0.8,0.9,0.95)]
    print(f"{len(pairs)} synthetic labeled pairs; 12 positive and 12 negative.")
    print("Pairs are evaluated independently; a child belongs to its parent series.")
    print("Precision = TP/(TP+FP); recall = TP/(TP+FN).")
    print("This small authored fixture is a development check, not a population estimate.")
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
