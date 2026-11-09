#!/usr/bin/env python3
"""Validate and summarise mahabharata_characters.ttl.

Steps:
  1. Parse the Turtle (syntax check).
  2. Run the SHACL shapes in shapes.ttl with RDFS inference (pyshacl).
  3. Check that every IRI used as a relation target or hierarchy parent is declared.
  4. Print counts recomputed from the graph and a few example traversals.

Usage: python scripts/validate.py [path/to/mahabharata_characters.ttl]
Exit code 0 when the graph conforms, 1 otherwise.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import SKOS

ROOT = Path(__file__).resolve().parents[1]
MBH = Namespace("https://mahabharata.tanay.uk/characters#")
MBHX = Namespace("https://mahabharata.tanay.uk/schema#")
SCHEME = URIRef("https://mahabharata.tanay.uk/characters")


def load(path: Path) -> Graph:
    g = Graph()
    g.parse(path, format="turtle")
    return g


def shacl(data: Graph, shapes_path: Path) -> bool:
    shapes = load(shapes_path)
    conforms, _report_graph, report_text = validate(
        data,
        shacl_graph=shapes,
        inference="rdfs",
        abort_on_first=False,
        meta_shacl=True,
        advanced=True,
        allow_warnings=False,
    )
    print("SHACL:", "conforms" if conforms else "VIOLATIONS")
    if not conforms:
        print(report_text)
    return conforms


def dangling(g: Graph) -> list[str]:
    """IRIs in the mbh: namespace that are used but never declared with a type."""
    declared = {s for s in g.subjects(RDF.type, None) if str(s).startswith(str(MBH))}
    used = set()
    for s, p, o in g:
        for node in (s, o):
            if isinstance(node, URIRef) and str(node).startswith(str(MBH)):
                used.add(node)
    return sorted(str(u).replace(str(MBH), "mbh:") for u in used - declared)


def label(g: Graph, node) -> str:
    for lbl in g.objects(node, SKOS.prefLabel):
        if getattr(lbl, "language", None) == "en":
            return str(lbl)
    return str(node)


def summary(g: Graph) -> None:
    characters = set(g.subjects(RDF.type, MBHX.Character))
    groupings = set(g.subjects(RDF.type, MBHX.Grouping))
    collections = set(g.subjects(RDF.type, SKOS.Collection)) | set(g.subjects(RDF.type, SKOS.OrderedCollection))
    print(f"\nTriples: {len(g)}")
    print(f"Characters: {len(characters)}   Groupings: {len(groupings)}   Collections: {len(collections)}")
    print(f"Top concepts: {len(list(g.objects(SCHEME, SKOS.hasTopConcept)))}")

    langs = Counter(lbl.language for lbl in g.objects(None, SKOS.prefLabel))
    print("prefLabels by language:", dict(sorted(langs.items())))
    print(f"altLabels: {len(list(g.triples((None, SKOS.altLabel, None))))}   "
          f"hiddenLabels: {len(list(g.triples((None, SKOS.hiddenLabel, None))))}")

    rel_counts = Counter()
    for p in g.subjects(RDFS.subPropertyOf, MBHX.characterRelation):
        n = len(list(g.triples((None, p, None))))
        if n:
            rel_counts[str(p).replace(str(MBHX), "mbhx:")] = n
    print("Character relations stated:", dict(sorted(rel_counts.items())))
    print(f"Characters with a war-day: {len(list(g.subjects(MBHX.fellOnWarDay, None)))}")

    exact = {s for s in g.subjects(SKOS.exactMatch, None) if s in characters}
    close = {s for s in g.subjects(SKOS.closeMatch, None) if s in characters}
    unmapped = characters - exact - close
    print(f"Characters with exactMatch: {len(exact)}   closeMatch only: {len(close - exact)}   "
          f"neither (seeAlso only): {len(unmapped)}")
    if unmapped:
        print("  seeAlso only:", ", ".join(sorted(label(g, c) for c in unmapped)))

    poly = sorted(label(g, c) for c in characters if len(list(g.objects(c, SKOS.broader))) > 1)
    print(f"Characters under more than one grouping ({len(poly)}):", ", ".join(poly))

    print("\nExample traversals (SPARQL over the stated triples, no inference):")
    q1 = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX mbhx: <https://mahabharata.tanay.uk/schema#>
        PREFIX mbh:  <https://mahabharata.tanay.uk/characters#>
        SELECT ?name WHERE { ?c mbhx:killedBy mbh:arjuna ; skos:prefLabel ?name . FILTER(lang(?name)="en") } ORDER BY ?name
    """
    print("  Killed by Arjuna:", ", ".join(str(r.name) for r in g.query(q1)))
    q2 = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX mbhx: <https://mahabharata.tanay.uk/schema#>
        PREFIX mbh:  <https://mahabharata.tanay.uk/characters#>
        SELECT ?name WHERE { ?c mbhx:childOf+ mbh:shantanu ; skos:prefLabel ?name . FILTER(lang(?name)="en") } ORDER BY ?name
    """
    print("  Descendants of Shantanu by stated parentage:", ", ".join(str(r.name) for r in g.query(q2)))
    q3 = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX mbhx: <https://mahabharata.tanay.uk/schema#>
        PREFIX mbh:  <https://mahabharata.tanay.uk/characters#>
        SELECT ?name WHERE { ?c skos:broader+ mbh:house-of-kuru ; a mbhx:Character ; skos:prefLabel ?name . FILTER(lang(?name)="en") }
    """
    print(f"  Characters under House of Kuru (transitive): {len(list(g.query(q3)))}")
    q4 = """
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX mbhx: <https://mahabharata.tanay.uk/schema#>
        PREFIX mbh:  <https://mahabharata.tanay.uk/characters#>
        SELECT ?name WHERE { ?c mbhx:childOf mbh:vayu ; skos:prefLabel ?name . FILTER(lang(?name)="en") } ORDER BY ?name
    """
    print("  Sons of Vayu (siblings by shared parent):", ", ".join(str(r.name) for r in g.query(q4)))


def main() -> int:
    data_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "mahabharata_characters.ttl"
    g = load(data_path)
    print(f"Parsed {data_path.name}: {len(g)} triples")
    ok = shacl(g, ROOT / "shapes.ttl")
    missing = dangling(g)
    if missing:
        ok = False
        print("Undeclared mbh: IRIs:", ", ".join(missing))
    else:
        print("Undeclared mbh: IRIs: none")
    summary(g)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
