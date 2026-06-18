from __future__ import annotations

import json

from src.collectors.mercadolivre import MercadoLivrePriceCollector


def main() -> None:
    collector = MercadoLivrePriceCollector()
    report = collector.diagnose()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
