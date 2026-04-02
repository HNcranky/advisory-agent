# ingestion/main.py
"""
Entry point for the ingestion pipeline.

Usage:
    python -m ingestion.main                    # Run for HUST programs
    python -m ingestion.main --school hust      # Run for all HUST sources
    python -m ingestion.main --url <url>        # Run for a single URL
"""

import sys
import json
import logging
import argparse
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ingestion.pipeline.ingestion_pipeline import IngestionPipeline
from ingestion.registry.source_registry import SourceRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingestion")


def main():
    parser = argparse.ArgumentParser(
        description="Admission Data Ingestion Pipeline"
    )
    parser.add_argument(
        "--school",
        type=str,
        help="School ID to crawl all sources (e.g. 'hust')",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Specific source ID to crawl",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Single URL to process",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    pipeline = IngestionPipeline()

    records = []

    if args.url:
        logger.info(f"Processing single URL: {args.url}")
        records = pipeline.run_single_url(args.url)

    elif args.source:
        source = pipeline.registry.get_source(args.source)
        if source:
            logger.info(f"Processing source: {args.source}")
            records = pipeline.run_for_source(source)
        else:
            logger.error(f"Source not found: {args.source}")
            sys.exit(1)

    elif args.school:
        logger.info(f"Processing school: {args.school}")
        records = pipeline.run_for_school(args.school)

    else:
        # Default: HUST program listing
        logger.info("Default: Processing HUST program listing")
        source = pipeline.registry.get_source("hust_program_listing")
        if source:
            records = pipeline.run_for_source(source)
        else:
            logger.error("HUST program listing source not found in registry")
            sys.exit(1)

    # ─── Output results ─────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"Pipeline complete: {len(records)} normalized records")
    logger.info(f"{'='*60}")

    # Serialize
    output_data = []
    for record in records:
        output_data.append(record.model_dump(
            mode="json",
            exclude_none=True,
        ))

    # Print summary
    for i, record in enumerate(records):
        logger.info(
            f"\n[{i+1}] {record.program_name_raw or 'N/A'} "
            f"({record.program_id or 'N/A'})"
        )
        if record.program_name_canonical:
            logger.info(
                f"    → Canonical: {record.program_name_canonical}"
            )
        if record.admission_method:
            logger.info(f"    Method: {record.admission_method}")
        if record.subject_combinations:
            combos = ", ".join(
                c.code for c in record.subject_combinations
            )
            logger.info(f"    Combos: {combos}")
        if record.quota:
            logger.info(f"    Quota: {record.quota.model_dump()}")

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        logger.info(f"\nSaved to: {output_path}")
    else:
        # Print JSON to stdout
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()