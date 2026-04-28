from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

RESULT_FIELDS = [
    'name', 'e_fr', 'e_thd', 'e_match', 'e_unc', 'w_conf', 'e_total',
    'n_sources', 'thd_available', 'match_available', 'price_brl', 'score',
    'score_lower_95', 'score_upper_95', 'confidence_interval',
    'peakiness', 'impedance_interaction',
]


def normalize_result_row(result: Mapping[str, object]) -> dict:
    row = {field: result.get(field) for field in RESULT_FIELDS}
    ci = result.get('confidence_interval')
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        row['score_lower_95'] = ci[0]
        row['score_upper_95'] = ci[1]
    return row


def write_results_csv(results: Iterable[Mapping[str, object]], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [normalize_result_row(r) for r in results]
    with output_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def load_results(path: str | Path):
    path = Path(path)
    text = path.read_text(encoding='utf-8')
    stripped = text.lstrip()
    if not stripped:
        return []
    if path.suffix.lower() == '.jsonl':
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and 'results' in data and isinstance(data['results'], list):
        return data['results']
    raise ValueError('Unsupported input format. Use JSON list, JSONL, or a dict containing "results".')


def build_dataset(input_path: str | Path, output_path: str | Path) -> Path:
    results = load_results(input_path)
    return write_results_csv(results, output_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a ranked headphone dataset CSV.')
    parser.add_argument('input', help='JSON list, JSONL, or dict with a results array')
    parser.add_argument('output', help='Destination CSV path')
    args = parser.parse_args(argv)
    build_dataset(args.input, args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
