"""End-to-end pipeline orchestration (Bronze -> Silver -> Merge -> Warehouse -> Gold)."""

import argparse
import sys


def run_pipeline(species_names: list[str], batch_id: str | None = None) -> dict:
    raise NotImplementedError


def main():
    parser = argparse.ArgumentParser(description="Shark Knowledge Medallion Pipeline")
    parser.add_argument("--batch", choices=["seed"], help="Run with seed species batch")
    parser.add_argument("--species", nargs="+", help="List of scientific names to process")
    parser.add_argument("--species-file", type=str, help="File with species names (one per line)")
    args = parser.parse_args()

    if args.batch == "seed":
        from src.config.seed_species import SEED_SPECIES
        species = [s["scientific_name"] for s in SEED_SPECIES]
    elif args.species:
        species = args.species
    elif args.species_file:
        with open(args.species_file) as f:
            species = [line.strip() for line in f if line.strip()]
    else:
        parser.print_help()
        sys.exit(1)

    result = run_pipeline(species)
    print(result)


if __name__ == "__main__":
    main()
