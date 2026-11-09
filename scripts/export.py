#!/usr/bin/env python3
"""Serialise the concept scheme into other RDF syntaxes.

The Turtle file is the source of truth and the only serialisation kept in the
repository. This script writes equivalent RDF/XML, JSON-LD and N-Triples files
to dist/ (ignored by git) for tools that want them.

Usage: python scripts/export.py [--out DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["mahabharata_characters.ttl", "shapes.ttl"]
FORMATS = {"xml": ".rdf", "json-ld": ".jsonld", "nt": ".nt"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "dist", help="output directory (default: dist/)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        g = Graph()
        g.parse(ROOT / name, format="turtle")
        stem = Path(name).stem
        for fmt, ext in FORMATS.items():
            target = args.out / f"{stem}{ext}"
            g.serialize(destination=str(target), format=fmt, encoding="utf-8")
            print(f"{target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}  ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
