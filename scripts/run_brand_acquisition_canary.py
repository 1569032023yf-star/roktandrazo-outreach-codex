"""Conservative public-only Phase 4B.1A parser canary; no database/email writes."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brand_acquisition import AcquisitionPipeline, PipelineConfig


OUTPUT = ROOT / "output" / "brand_acquisition" / "phase4b1a"
SOURCE_PAGES = {
    "tiktok_shop": [
        "https://shop.tiktok.com/us/store/sleazy-greetings/7495078245334616103",
    ],
    "amazon": [
        "https://www.amazon.com/gp/bestsellers/office-products/1069296",
    ],
    "wholesale": [
        "https://external.faire.com/suppliers/Paper%20%26%20Novelty/subcategory/Greeting%20Cards",
        "https://www.faire.com/suppliers/Paper%20%26%20Novelty/subcategory/Greeting%20Cards/Everyday",
    ],
}


def main() -> int:
    pipeline = AcquisitionPipeline(OUTPUT, PipelineConfig())
    result = pipeline.run_sources(SOURCE_PAGES)
    result["DATA_BOUNDARY"] = "public discovery only; owner/history/email gates remain fail-closed"
    result["PRODUCTION_DB_WRITES"] = 0
    result["SMTP_CONNECTIONS"] = 0
    result["EMAILS_SENT"] = 0
    (OUTPUT / "canary_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2))
    print("Output:", OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
