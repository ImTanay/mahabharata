#!/usr/bin/env python3
"""Render the specification website from the data.

Writes
  index.html        the specification: one page in the manner of a W3C vocabulary
                    specification such as PROV-O, with the model at a glance, the
                    full hierarchy and a cross-reference entry for every term
  characters.html   the namespace documents for mbh:, mbhx: and mbsh:. Each lists
  schema.html       its terms and forwards a browser to the matching anchor of
  shapes.html       index.html, so that every IRI of the scheme resolves

Usage:
  python scripts/render_site.py          write the files
  python scripts/render_site.py --check  exit 1 if any file would change (used in CI)

Everything is derived from mahabharata_characters.ttl and shapes.ttl, so the
page cannot disagree with the data. The generator refuses to write a page with
a duplicate id, a dangling internal link, a statement it did not render, or
ill-formed markup.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, FOAF, OWL, SH, SKOS, XSD

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_docs import PREFIXES as SPARQL_PREFIXES, QUERIES, characters_below  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TTL = ROOT / "mahabharata_characters.ttl"
SHAPES = ROOT / "shapes.ttl"

SITE_URL = "https://mahabharata.tanay.uk/"
REPO_URL = "https://github.com/ImTanay/mahabharata"  # empty string leaves the Repository line out
AUTHOR = "Tanay Aggarwal"

MB = Namespace(SITE_URL)
MBH = Namespace(SITE_URL + "characters#")
MBHX = Namespace(SITE_URL + "schema#")
MBSH = Namespace(SITE_URL + "shapes#")
SCHEME = MB["characters"]
ONTOLOGY = MB["schema"]
WD = "http://www.wikidata.org/entity/"
DBR = "http://dbpedia.org/resource/"
WP = "https://en.wikipedia.org/wiki/"

# Prefixes used in this document, in the order of the namespace table.
PREFIXES = [
    ("mb", str(MB), "the concept scheme and the extension schema"),
    ("mbh", str(MBH), "concepts and collections of the scheme"),
    ("mbhx", str(MBHX), "classes and properties of the extension schema"),
    ("mbsh", str(MBSH), "the SHACL shapes"),
    ("skos", str(SKOS), "SKOS [SKOS-REFERENCE]"),
    ("rdf", str(RDF), "RDF [RDF11-CONCEPTS]"),
    ("rdfs", str(RDFS), "RDF Schema [RDF-SCHEMA]"),
    ("owl", str(OWL), "OWL 2 [OWL2-OVERVIEW]"),
    ("xsd", str(XSD), "XML Schema datatypes [XMLSCHEMA11-2]"),
    ("dcterms", str(DCTERMS), "Dublin Core terms [DCTERMS]"),
    ("foaf", str(FOAF), "FOAF [FOAF]"),
    ("sh", str(SH), "SHACL [SHACL]"),
    ("wd", WD, "Wikidata entities [WIKIDATA]"),
    ("dbr", DBR, "DBpedia resources [DBPEDIA]"),
    ("wp", WP, "articles of the English Wikipedia [WIKIPEDIA]"),
]

# Bibliography: key, title, details, URL. Keys are cited in the text as [KEY].
REFERENCES = [
    ("SKOS-REFERENCE", "SKOS Simple Knowledge Organization System Reference",
     "Alistair Miles, Sean Bechhofer. W3C Recommendation, 18 August 2009.", "https://www.w3.org/TR/skos-reference/"),
    ("SKOS-PRIMER", "SKOS Simple Knowledge Organization System Primer",
     "Antoine Isaac, Ed Summers. W3C Working Group Note, 18 August 2009.", "https://www.w3.org/TR/skos-primer/"),
    ("SHACL", "Shapes Constraint Language (SHACL)",
     "Holger Knublauch, Dimitris Kontokostas. W3C Recommendation, 20 July 2017.", "https://www.w3.org/TR/shacl/"),
    ("TURTLE", "RDF 1.1 Turtle",
     "Eric Prud'hommeaux, Gavin Carothers. W3C Recommendation, 25 February 2014.", "https://www.w3.org/TR/turtle/"),
    ("RDF11-CONCEPTS", "RDF 1.1 Concepts and Abstract Syntax",
     "Richard Cyganiak, David Wood, Markus Lanthaler. W3C Recommendation, 25 February 2014.",
     "https://www.w3.org/TR/rdf11-concepts/"),
    ("RDF-SCHEMA", "RDF Schema 1.1",
     "Dan Brickley, R.V. Guha. W3C Recommendation, 25 February 2014.", "https://www.w3.org/TR/rdf-schema/"),
    ("OWL2-OVERVIEW", "OWL 2 Web Ontology Language Document Overview (Second Edition)",
     "W3C OWL Working Group. W3C Recommendation, 11 December 2012.", "https://www.w3.org/TR/owl2-overview/"),
    ("XMLSCHEMA11-2", "W3C XML Schema Definition Language (XSD) 1.1 Part 2: Datatypes",
     "David Peterson et al. W3C Recommendation, 5 April 2012.", "https://www.w3.org/TR/xmlschema11-2/"),
    ("SPARQL11-QUERY", "SPARQL 1.1 Query Language",
     "Steve Harris, Andy Seaborne. W3C Recommendation, 21 March 2013.", "https://www.w3.org/TR/sparql11-query/"),
    ("DCTERMS", "DCMI Metadata Terms", "Dublin Core Metadata Initiative, 20 January 2020.",
     "https://www.dublincore.org/specifications/dublin-core/dcmi-terms/"),
    ("FOAF", "FOAF Vocabulary Specification 0.99", "Dan Brickley, Libby Miller, 14 January 2014.",
     "http://xmlns.com/foaf/spec/"),
    ("BCP47", "Tags for Identifying Languages", "Addison Phillips, Mark Davis. IETF BCP 47, September 2009.",
     "https://www.rfc-editor.org/info/bcp47"),
    ("PROV-O", "PROV-O: The PROV Ontology",
     "Timothy Lebo, Satya Sahoo, Deborah McGuinness. W3C Recommendation, 30 April 2013. "
     "The layout of this document follows it.", "https://www.w3.org/TR/prov-o/"),
    ("WIKIPEDIA", "Mahabharata",
     "Wikipedia, The Free Encyclopedia. CC BY-SA 4.0. The source of the content of the scheme, together with "
     "the character articles it links to.", "https://en.wikipedia.org/wiki/Mahabharata"),
    ("WIKIPEDIA-LIST", "List of characters in the Mahabharata", "Wikipedia, The Free Encyclopedia.",
     "https://en.wikipedia.org/wiki/List_of_characters_in_the_Mahabharata"),
    ("WIKIDATA", "Wikidata", "Wikimedia Foundation. Identifiers were resolved through the Wikipedia API.",
     "https://www.wikidata.org/"),
    ("DBPEDIA", "DBpedia", "DBpedia Association.", "https://www.dbpedia.org/"),
]


# --------------------------------------------------------------------------- helpers

def esc(s) -> str:
    return escape(str(s), quote=True)


def a(href: str, text: str, cls: str = "", title: str = "") -> str:
    attrs = f' class="{cls}"' if cls else ""
    attrs += f' title="{esc(title)}"' if title else ""
    return f'<a href="{esc(href)}"{attrs}>{text}</a>'


def code(text) -> str:
    return f"<code>{esc(text)}</code>"


def qname(node) -> str:
    s = str(node)
    best = None
    for prefix, ns, _ in PREFIXES:
        if s.startswith(ns) and (best is None or len(ns) > len(best[1])):
            best = (prefix, ns)
    return f"{best[0]}:{s[len(best[1]):]}" if best else s


def is_internal(node) -> bool:
    return isinstance(node, URIRef) and str(node).startswith(SITE_URL)


def anchor(node) -> str:
    """The id of a term's entry: the fragment of a hash IRI, the last path segment otherwise."""
    s = str(node)
    frag = s.rsplit("#", 1)[1] if "#" in s else s.rsplit("/", 1)[1]
    return frag or "shapes"


def lits(g: Graph, node, prop, lang: str | None = None) -> list[str]:
    found = [o for o in g.objects(node, prop)
             if isinstance(o, Literal) and (lang is None or o.language == lang)]
    return [str(o) for o in sorted(found, key=lambda o: (o.language or "", str(o)))]


def lit1(g: Graph, node, prop, lang: str = "en") -> str | None:
    found = lits(g, node, prop, lang)
    return found[0] if found else None


def en(g: Graph, node) -> str:
    return (lit1(g, node, SKOS.prefLabel) or lit1(g, node, RDFS.label)
            or lit1(g, node, DCTERMS.title) or qname(node))


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def inline_md(text: str) -> str:
    """Escape text and turn `code` spans into <code>, for the explanations of the SPARQL cookbook."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


def cites(text: str) -> str:
    """Turn [KEY] into a link to the bibliography entry."""
    keys = {k for k, *_ in REFERENCES}
    return re.sub(r"\[([A-Z0-9-]+)\]",
                  lambda m: a(f"#bib-{m.group(1)}", f"[{m.group(1)}]", "bib") if m.group(1) in keys else m.group(0),
                  text)


def shape_name(shape) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", anchor(shape).removesuffix("Shape")).split()
    return " ".join([words[0]] + [w.lower() for w in words[1:]]) if words else "Shapes graph"


def simple_table(headers: list[str], rows: list[list[str]]) -> str:
    thead = "".join(f"<th>{h}</th>" for h in headers)
    tbody = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="simple"><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>'


def term_order(text: str) -> dict[str, int]:
    """Position of each mb:/mbh:/mbhx:/mbsh: subject in the Turtle, so listings follow the author's order."""
    order: dict[str, int] = {}
    for m in re.finditer(r"^((?:mb|mbh|mbhx|mbsh):[A-Za-z0-9-]*)\s+a\s", text, re.M):
        order.setdefault(m.group(1), len(order))
    return order


# --------------------------------------------------------------------------- context

class Ctx:
    """The two graphs, the author's ordering, and the derived sets every section needs."""

    def __init__(self, g: Graph, sg: Graph, order: dict[str, int]):
        self.g, self.sg, self.order = g, sg, order
        self.ids: set[str] = set()
        self.memo: dict = {}
        self.chars = self.sorted(g.subjects(RDF.type, MBHX.Character))
        self.groups = self.sorted(g.subjects(RDF.type, MBHX.Grouping))
        self.ordered = set(g.subjects(RDF.type, SKOS.OrderedCollection))
        self.colls = self.sorted(set(g.subjects(RDF.type, SKOS.Collection)) | self.ordered)
        self.tops = self.sorted(g.objects(SCHEME, SKOS.hasTopConcept))
        self.rel_props = self.sorted(g.subjects(RDFS.subPropertyOf, MBHX.characterRelation))
        self.stated = [p for p in self.rel_props if (None, p, None) in g]
        self.inverse = {p: g.value(p, OWL.inverseOf) for p in self.rel_props}
        self.symmetric = {p for p in self.rel_props if (p, RDF.type, OWL.SymmetricProperty) in g}
        self.classes = self.sorted(g.subjects(RDF.type, OWL.Class))
        self.props = self.sorted(set(g.subjects(RDF.type, OWL.ObjectProperty))
                                 | set(g.subjects(RDF.type, OWL.DatatypeProperty)))
        self.shapes = self.sorted(sg.subjects(RDF.type, SH.NodeShape))

    def key(self, node):
        return (self.order.get(qname(node), 10**6), en(self.g, node))

    def sorted(self, nodes) -> list:
        return sorted(set(nodes), key=self.key)

    def by_label(self, nodes) -> list:
        return sorted(set(nodes), key=lambda n: en(self.g, n).lower())

    def uid(self, id_: str) -> str:
        if id_ in self.ids:
            raise SystemExit(f"render_site: duplicate id #{id_}")
        self.ids.add(id_)
        return id_

    def covered(self, node, handled: set, graph: Graph | None = None) -> None:
        """Refuse to leave a statement about a term out of its entry."""
        missing = set((graph or self.g).predicates(node, None)) - handled
        if missing:
            raise SystemExit(f"render_site: {qname(node)} has statements not shown in its entry: "
                             + ", ".join(sorted(qname(p) for p in missing)))

    def below(self, grouping) -> set:
        return characters_below(self.g, grouping, self.memo)

    def count(self, prop) -> int:
        return sum(1 for _ in self.g.triples((None, prop, None)))


# --------------------------------------------------------------------------- cells

def term_link(ctx: Ctx, node, label: bool = True) -> str:
    """A link to a term: internal terms go to their entry, external IRIs to themselves."""
    if str(node).startswith(str(MBSH)):
        text = esc(shape_name(node)) if label else code(qname(node))
    else:
        text = esc(en(ctx.g, node)) if label else code(qname(node))
    return a("#" + anchor(node), text) if is_internal(node) else a(str(node), text)


def code_link(ctx: Ctx, node) -> str:
    return term_link(ctx, node, label=False)


def iri_cell(node) -> str:
    return a(str(node), esc(str(node)), "iri")


def types_cell(ctx: Ctx, node, graph: Graph | None = None) -> str:
    g = graph or ctx.g
    return ", ".join(code_link(ctx, t) for t in sorted(g.objects(node, RDF.type), key=qname))


def labels_cell(g: Graph, node, prop) -> str:
    groups = []
    for lang in ("en", "sa-Deva", "sa-Latn"):
        vals = lits(g, node, prop, lang)
        if vals:
            spans = ", ".join(f'<span lang="{lang}">{esc(v)}</span>' for v in vals)
            groups.append(f'<span class="lt">{lang}</span>{spans}')
    return "<br/>".join(groups)


def text_cell(g: Graph, node, prop) -> str:
    return "<br/>".join(f'<span lang="en">{esc(v)}</span>' for v in lits(g, node, prop, "en"))


def name_list(ctx: Ctx, nodes) -> str:
    return ", ".join(term_link(ctx, n) for n in ctx.by_label(nodes))


def code_list(ctx: Ctx, nodes) -> str:
    return ", ".join(code_link(ctx, n) for n in sorted(set(nodes), key=qname))


def url_list(g: Graph, node, prop) -> str:
    return ", ".join(a(str(o), esc(str(o))) for o in sorted(g.objects(node, prop), key=str))


def ext_cell(ctx: Ctx, node, prop) -> str:
    out = []
    for o in sorted(ctx.g.objects(node, prop), key=str):
        s = str(o)
        if s.startswith(WD):
            out.append(a(s, "Wikidata " + code(s[len(WD):])))
        elif s.startswith(DBR):
            out.append(a(s, "DBpedia " + code(s[len(DBR):])))
        elif s.startswith(WP):
            out.append(a(s, "Wikipedia: " + esc(s[len(WP):].replace("_", " "))))
        else:
            out.append(a(s, esc(s)))
    return ", ".join(out)


def path_to_top(ctx: Ctx, grouping) -> list:
    path = [grouping]
    while True:
        up = ctx.sorted(ctx.g.objects(path[-1], SKOS.broader))
        if not up:
            return list(reversed(path))
        path.append(up[0])


def broader_cell(ctx: Ctx, node) -> str:
    return "<br/>".join(" › ".join(term_link(ctx, p) for p in path_to_top(ctx, b))
                        for b in ctx.sorted(ctx.g.objects(node, SKOS.broader)))


def sanskrit(g: Graph, node) -> str:
    sa = " · ".join(v for v in (lit1(g, node, SKOS.prefLabel, "sa-Deva"), lit1(g, node, SKOS.prefLabel, "sa-Latn")) if v)
    return f' <span class="sa">{esc(sa)}</span>' if sa else ""


def entry(ctx: Ctx, node, kind: str, heading: str, rows: list[tuple[str, str]], sub: str = "") -> str:
    """One cross-reference entry: a heading band and a table of the term's statements. Empty rows are dropped."""
    id_ = ctx.uid(anchor(node))
    trs = "".join(f'<tr><th scope="row">{k}</th><td>{v}</td></tr>' for k, v in rows if v)
    head = (f'<h4><span class="kind">{esc(kind)}</span> <span class="lbl">{heading}</span>'
            f'<code class="qn">{esc(qname(node))}</code>{sub}'
            f'{a("#" + id_, "§", "self", "Link to this entry")}</h4>')
    return f'<section class="term {kind.lower()}" id="{id_}">\n{head}\n<table class="definition">{trs}</table>\n</section>'


# --------------------------------------------------------------------------- entries: concepts and collections

def relation_rows(ctx: Ctx, c) -> list[tuple[str, str]]:
    """Stated relations in the direction the property names, then the other direction, inferred."""
    g, rows = ctx.g, []
    for p in ctx.stated:
        label = esc(en(g, p).capitalize())
        forward, backward = set(g.objects(c, p)), set(g.subjects(p, c))
        if p in ctx.symmetric:
            if forward | backward:
                rows.append((label, name_list(ctx, forward | backward)))
            continue
        if forward:
            rows.append((label, name_list(ctx, forward)))
        if backward:
            inv = ctx.inverse[p]
            rows.append((f'{esc(en(g, inv).capitalize())} <span class="inf">inferred from {code(qname(p))}</span>',
                         name_list(ctx, backward)))
    return rows


def member_of_cell(ctx: Ctx, c) -> str:
    out = []
    for coll in ctx.colls:
        if (coll, SKOS.member, c) not in ctx.g:
            continue
        text = term_link(ctx, coll)
        if coll in ctx.ordered:
            members = list(Collection(ctx.g, ctx.g.value(coll, SKOS.memberList)))
            text += f' <span class="count">({members.index(c) + 1} of {len(members)})</span>'
        out.append(text)
    return "<br/>".join(out)


CHARACTER_PREDICATES = {RDF.type, SKOS.prefLabel, SKOS.altLabel, SKOS.hiddenLabel, SKOS.definition, SKOS.note,
                        SKOS.scopeNote, SKOS.inScheme, SKOS.broader, MBHX.fellOnWarDay, SKOS.exactMatch,
                        SKOS.closeMatch, FOAF.isPrimaryTopicOf, RDFS.seeAlso}
GROUPING_PREDICATES = {RDF.type, SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.scopeNote, SKOS.inScheme,
                       SKOS.topConceptOf, SKOS.broader, SKOS.related, SKOS.exactMatch, SKOS.closeMatch,
                       FOAF.isPrimaryTopicOf, RDFS.seeAlso}
COLLECTION_PREDICATES = {RDF.type, SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.inScheme, SKOS.member,
                         SKOS.memberList}


def character_entry(ctx: Ctx, c) -> str:
    g = ctx.g
    war = g.value(c, MBHX.fellOnWarDay)
    rows = [("IRI", iri_cell(c)), ("Type", types_cell(ctx, c)),
            ("Preferred label", labels_cell(g, c, SKOS.prefLabel)),
            ("Alternative labels", labels_cell(g, c, SKOS.altLabel)),
            ("Hidden labels", labels_cell(g, c, SKOS.hiddenLabel)),
            ("Definition", text_cell(g, c, SKOS.definition)),
            ("Note", text_cell(g, c, SKOS.note)),
            ("Scope note", text_cell(g, c, SKOS.scopeNote)),
            ("In scheme", code_link(ctx, SCHEME)),
            ("Broader", broader_cell(ctx, c))]
    rows += relation_rows(ctx, c)
    rows += [("Fell on war day", f"day {int(war)} of 18" if war is not None else ""),
             ("Member of", member_of_cell(ctx, c)),
             ("Exact match", ext_cell(ctx, c, SKOS.exactMatch)),
             ("Close match", ext_cell(ctx, c, SKOS.closeMatch)),
             ("Primary topic of", ext_cell(ctx, c, FOAF.isPrimaryTopicOf)),
             ("See also", ext_cell(ctx, c, RDFS.seeAlso))]
    ctx.covered(c, CHARACTER_PREDICATES | set(ctx.rel_props))
    return entry(ctx, c, "Character", esc(en(g, c)), rows, sanskrit(g, c))


def grouping_entry(ctx: Ctx, gr) -> str:
    g = ctx.g
    children = ctx.sorted(g.subjects(SKOS.broader, gr))
    narrower = [n for n in children if n in ctx.groups]
    direct = [n for n in children if n in ctx.chars]
    related = set(g.objects(gr, SKOS.related)) | set(g.subjects(SKOS.related, gr))
    rows = [("IRI", iri_cell(gr)), ("Type", types_cell(ctx, gr)),
            ("Preferred label", labels_cell(g, gr, SKOS.prefLabel)),
            ("Alternative labels", labels_cell(g, gr, SKOS.altLabel)),
            ("Definition", text_cell(g, gr, SKOS.definition)),
            ("Scope note", text_cell(g, gr, SKOS.scopeNote)),
            ("In scheme", code_link(ctx, SCHEME)),
            ("Top concept of", code_link(ctx, SCHEME) if (gr, SKOS.topConceptOf, SCHEME) in g else ""),
            ("Broader", broader_cell(ctx, gr)),
            ("Narrower groupings", ", ".join(term_link(ctx, n) for n in narrower)),
            (f'Characters placed here <span class="count">({len(direct)} directly, {len(ctx.below(gr))} in all)</span>',
             name_list(ctx, direct)),
            ("Related", name_list(ctx, related)),
            ("Exact match", ext_cell(ctx, gr, SKOS.exactMatch)),
            ("Close match", ext_cell(ctx, gr, SKOS.closeMatch)),
            ("Primary topic of", ext_cell(ctx, gr, FOAF.isPrimaryTopicOf)),
            ("See also", ext_cell(ctx, gr, RDFS.seeAlso))]
    ctx.covered(gr, GROUPING_PREDICATES)
    return entry(ctx, gr, "Grouping", esc(en(g, gr)), rows, sanskrit(g, gr))


def collection_entry(ctx: Ctx, coll) -> str:
    g = ctx.g
    if coll in ctx.ordered:
        members = list(Collection(g, g.value(coll, SKOS.memberList)))
        cell = "<ol>" + "".join(f"<li>{term_link(ctx, m)}</li>" for m in members) + "</ol>"
    else:
        cell = name_list(ctx, g.objects(coll, SKOS.member))
    n = sum(1 for _ in g.objects(coll, SKOS.member))
    rows = [("IRI", iri_cell(coll)), ("Type", types_cell(ctx, coll)),
            ("Preferred label", labels_cell(g, coll, SKOS.prefLabel)),
            ("Alternative labels", labels_cell(g, coll, SKOS.altLabel)),
            ("Definition", text_cell(g, coll, SKOS.definition)),
            ("In scheme", code_link(ctx, SCHEME)),
            (f'Members <span class="count">({n}{", in order" if coll in ctx.ordered else ""})</span>', cell)]
    ctx.covered(coll, COLLECTION_PREDICATES)
    return entry(ctx, coll, "Collection", esc(en(g, coll)), rows)


# --------------------------------------------------------------------------- entries: scheme and schema

def scheme_entry(ctx: Ctx) -> str:
    g, s = ctx.g, SCHEME
    modified = g.value(s, DCTERMS.modified)
    rows = [("IRI", iri_cell(s)), ("Type", types_cell(ctx, s)),
            ("Title", text_cell(g, s, DCTERMS.title)),
            ("Description", text_cell(g, s, DCTERMS.description)),
            ("Version", code(g.value(s, OWL.versionInfo))),
            ("Created", esc(long_date(str(g.value(s, DCTERMS.created))))),
            ("Modified", esc(long_date(str(modified))) if modified is not None else ""),
            ("Languages", ", ".join(code(v) for v in lits(g, s, DCTERMS.language))),
            ("Sources", url_list(g, s, DCTERMS.source)),
            ("Conforms to", url_list(g, s, DCTERMS.conformsTo)),
            ("Licence", url_list(g, s, DCTERMS.license)),
            ("Homepage", url_list(g, s, FOAF.homepage)),
            ("Comment", text_cell(g, s, RDFS.comment)),
            ("Scope note", text_cell(g, s, SKOS.scopeNote)),
            ("Editorial note", text_cell(g, s, SKOS.editorialNote)),
            ("Top concepts", ", ".join(term_link(ctx, t) for t in ctx.tops))]
    ctx.covered(s, {RDF.type, DCTERMS.title, DCTERMS.description, OWL.versionInfo, DCTERMS.created, DCTERMS.modified,
                    DCTERMS.language, DCTERMS.source, DCTERMS.conformsTo, DCTERMS.license, FOAF.homepage,
                    RDFS.comment, SKOS.scopeNote, SKOS.editorialNote, SKOS.hasTopConcept})
    return entry(ctx, s, "Scheme", esc(en(g, s)), rows)


def ontology_entry(ctx: Ctx) -> str:
    g, s = ctx.g, ONTOLOGY
    rows = [("IRI", iri_cell(s)), ("Type", types_cell(ctx, s)),
            ("Title", text_cell(g, s, DCTERMS.title)),
            ("Version", code(g.value(s, OWL.versionInfo))),
            ("Comment", text_cell(g, s, RDFS.comment)),
            ("See also", url_list(g, s, RDFS.seeAlso)),
            ("Classes", ", ".join(code_link(ctx, c) for c in ctx.classes)),
            ("Properties", ", ".join(code_link(ctx, p) for p in ctx.props))]
    ctx.covered(s, {RDF.type, DCTERMS.title, OWL.versionInfo, RDFS.comment, RDFS.seeAlso})
    return entry(ctx, s, "Ontology", esc(en(g, s)), rows)


def class_entry(ctx: Ctx, cls) -> str:
    g = ctx.g
    instances = sum(1 for _ in g.subjects(RDF.type, cls))
    disjoint = set(g.objects(cls, OWL.disjointWith)) | set(g.subjects(OWL.disjointWith, cls))
    section = "#crossref-characters" if cls == MBHX.Character else "#crossref-groupings"
    rows = [("IRI", iri_cell(cls)), ("Type", types_cell(ctx, cls)),
            ("Label", text_cell(g, cls, RDFS.label)),
            ("Definition", text_cell(g, cls, SKOS.definition)),
            ("Subclass of", code_list(ctx, g.objects(cls, RDFS.subClassOf))),
            ("Disjoint with", code_list(ctx, disjoint)),
            ("In domain of", ", ".join(code_link(ctx, p) for p in ctx.sorted(g.subjects(RDFS.domain, cls)))),
            ("In range of", ", ".join(code_link(ctx, p) for p in ctx.sorted(g.subjects(RDFS.range, cls)))),
            ("Instances", a(section, f"{instances} in this scheme"))]
    ctx.covered(cls, {RDF.type, RDFS.label, SKOS.definition, RDFS.subClassOf, OWL.disjointWith})
    return entry(ctx, cls, "Class", esc(en(g, cls)), rows)


def example_statement(ctx: Ctx, p) -> str:
    triples = sorted(ctx.g.triples((None, p, None)), key=lambda t: (ctx.key(t[0]), str(t[2])))
    if not triples:
        return ""
    s, _, o = triples[0]
    obj = code_link(ctx, o) if isinstance(o, URIRef) else code(str(o))
    return f'<span class="turtle">{code_link(ctx, s)} {code_link(ctx, p)} {obj} .</span>'


def property_entry(ctx: Ctx, p) -> str:
    g = ctx.g
    n = ctx.count(p)
    inv = g.value(p, OWL.inverseOf)
    subs = ctx.sorted(g.subjects(RDFS.subPropertyOf, p))
    if n:
        stated = f"{n} statement{'s' if n != 1 else ''}"
    elif inv is not None:
        stated = (f"never stated: the data writes {code_link(ctx, inv)} on the other party, and this property "
                  f"follows by inference ({code_link(ctx, MBSH.InverseNotMaterialisedShape)} enforces it)")
    elif subs:
        stated = f"not used directly; {sum(ctx.count(s) for s in subs)} statements over its {len(subs)} sub-properties"
    else:
        stated = "none"
    kind = "Datatype property" if (p, RDF.type, OWL.DatatypeProperty) in g else "Object property"
    symmetric = "symmetric: stated once per pair and read in both directions" if p in ctx.symmetric else ""
    rows = [("IRI", iri_cell(p)), ("Type", types_cell(ctx, p)),
            ("Label", text_cell(g, p, RDFS.label)),
            ("Definition", text_cell(g, p, SKOS.definition)),
            ("Scope note", text_cell(g, p, SKOS.scopeNote)),
            ("Sub-property of", code_list(ctx, g.objects(p, RDFS.subPropertyOf))),
            ("Super-property of", ", ".join(code_link(ctx, s) for s in subs)),
            ("Inverse of", code_link(ctx, inv) if inv is not None else ""),
            ("Characteristics", symmetric),
            ("Domain", code_list(ctx, g.objects(p, RDFS.domain))),
            ("Range", code_list(ctx, g.objects(p, RDFS.range))),
            ("Stated in the data", stated),
            ("Example", example_statement(ctx, p))]
    ctx.covered(p, {RDF.type, RDFS.label, SKOS.definition, SKOS.scopeNote, RDFS.subPropertyOf, OWL.inverseOf,
                    RDFS.domain, RDFS.range})
    return entry(ctx, p, kind, esc(en(g, p)), rows)


# --------------------------------------------------------------------------- entries: SHACL shapes

SHACL_PARAMS = [SH.minCount, SH.maxCount, SH.qualifiedMinCount, SH.datatype, SH["class"], SH.nodeKind, SH.hasValue,
                SH.languageIn, SH.uniqueLang, SH.disjoint, SH.pattern, SH.minInclusive, SH.maxInclusive,
                SH.qualifiedValueShape]


def shacl_value(ctx: Ctx, v) -> str:
    sg = ctx.sg
    if isinstance(v, URIRef):
        return code_link(ctx, v)
    if isinstance(v, BNode):
        if (v, RDF.first, None) in sg:
            return ", ".join(shacl_value(ctx, item) for item in Collection(sg, v))
        if sg.value(v, SH.inversePath) is not None:
            return "^" + shacl_value(ctx, sg.value(v, SH.inversePath))
        return "[" + "; ".join(constraint_text(ctx, v)) + "]"
    return code(str(v))


def constraint_text(ctx: Ctx, shape) -> list[str]:
    parts = []
    for prm in SHACL_PARAMS:
        for v in ctx.sg.objects(shape, prm):
            parts.append(f"{code(qname(prm))} {shacl_value(ctx, v)}")
    return parts


def inline_checks(ctx: Ctx, shape) -> list[str]:
    sg, out = ctx.sg, []
    for ps in sg.objects(shape, SH.property):
        out.append(f"{shacl_value(ctx, sg.value(ps, SH.path))}: " + "; ".join(constraint_text(ctx, ps)))
    out += constraint_text(ctx, shape)
    return sorted(out)


def shape_checks(ctx: Ctx, shape) -> str:
    """Every constraint of a node shape as one list item, with the author's message where there is one."""
    sg, items = ctx.sg, []
    for v in sg.objects(shape, SH["class"]):
        items.append(f"the focus node is a {shacl_value(ctx, v)}")
    for ps in sg.objects(shape, SH.property):
        text = f"{shacl_value(ctx, sg.value(ps, SH.path))}: " + "; ".join(constraint_text(ctx, ps))
        msg = lit1(sg, ps, SH.message)
        items.append(text + (f'<br/><span class="msg">{esc(msg)}</span>' if msg else ""))
    for v in sg.objects(shape, SH["not"]):
        items.append("not: " + "; ".join(inline_checks(ctx, v)))
    for prm, word in ((SH.xone, "exactly one of"), (SH["or"], "at least one of")):
        for lst in sg.objects(shape, prm):
            alts = [" and ".join(inline_checks(ctx, alt)) for alt in Collection(sg, lst)]
            items.append(f"{word}: " + " | ".join(alts))
    for sq in sg.objects(shape, SH.sparql):
        items.append(f'SPARQL constraint: <span class="msg">{esc(lit1(sg, sq, SH.message) or "")}</span>')
    return "<ul>" + "".join(f"<li>{item}</li>" for item in sorted(items)) + "</ul>"


def shape_entry(ctx: Ctx, shape) -> str:
    sg, targets = ctx.sg, []
    for prm, word in ((SH.targetClass, "instances of"), (SH.targetSubjectsOf, "subjects of")):
        vals = sorted(sg.objects(shape, prm), key=qname)
        if vals:
            targets.append(f"{word} " + ", ".join(code_link(ctx, v) for v in vals))
    rows = [("IRI", iri_cell(shape)), ("Type", types_cell(ctx, shape, sg)),
            ("Targets", "; ".join(targets)),
            ("Comment", text_cell(sg, shape, RDFS.comment)),
            ("Checks", shape_checks(ctx, shape))]
    ctx.covered(shape, {RDF.type, SH.targetClass, SH.targetSubjectsOf, RDFS.comment, SH.property, SH["class"],
                        SH["not"], SH.xone, SH["or"], SH.sparql}, sg)
    return entry(ctx, shape, "Shape", esc(shape_name(shape)), rows)


def shapes_graph_entry(ctx: Ctx) -> str:
    sg, s = ctx.sg, URIRef(str(MBSH))
    decl = sorted(f"{code(sg.value(d, SH.prefix))} {a(str(sg.value(d, SH.namespace)), esc(sg.value(d, SH.namespace)))}"
                  for d in sg.objects(s, SH.declare))
    rows = [("IRI", iri_cell(s)), ("Type", types_cell(ctx, s, sg)),
            ("Declares prefixes", "<br/>".join(decl)),
            ("Shapes", ", ".join(code_link(ctx, sh) for sh in ctx.shapes))]
    ctx.covered(s, {RDF.type, SH.declare}, sg)
    return entry(ctx, s, "Shapes graph", "The shapes graph", rows)


# --------------------------------------------------------------------------- sections

class Section:
    def __init__(self, id_: str, title: str, body: str, children: list | None = None, appendix: bool = False):
        self.id, self.title, self.body, self.children, self.appendix = id_, title, body, children or [], appendix
        self.num = ""


def assign_numbers(sections: list[Section]) -> None:
    n = letter = 0
    for s in sections:
        if s.appendix:
            letter += 1
            s.num = chr(64 + letter)
        else:
            n += 1
            s.num = str(n)
        for i, c in enumerate(s.children, 1):
            c.num = f"{s.num}.{i}"


def secno(s: Section) -> str:
    """W3C style: a full stop after a top-level number (1.), none after a nested one (1.1)."""
    return f'<span class="secno">{s.num}{"." if "." not in s.num else ""}</span>'


def render_section(ctx: Ctx, s: Section, level: int) -> str:
    ctx.uid(s.id)
    parts = [f'<section id="{s.id}">', f'<h{level}>{secno(s)} {s.title}</h{level}>', s.body]
    parts += [render_section(ctx, c, level + 1) for c in s.children]
    parts.append("</section>")
    return "\n".join(parts)


def render_toc(sections: list[Section]) -> str:
    items = []
    for s in sections:
        inner = render_toc(s.children) if s.children else ""
        items.append(f'<li>{a("#" + s.id, f"{secno(s)} {s.title}")}{inner}</li>')
    return '<ol class="toc">' + "".join(items) + "</ol>"


def intro_body(ctx: Ctx) -> str:
    return cites(f"""<p>The <i>Mahabharata</i> is the Sanskrit epic of the dynastic war between the Pandavas and the Kauravas for the throne of Hastinapura. This scheme is a knowledge organisation system for its characters: the people, gods and other beings who act or are named in it. It is written in SKOS [SKOS-REFERENCE] and published as RDF 1.1 Turtle [TURTLE].</p>
<p>Every character is a <code>skos:Concept</code> placed under the lineage, royal house, order or class of being the epic gives it. Kinship and narrative ties between characters (parent, spouse, teacher, killer, charioteer, rebirth, curse) are sub-properties of <code>skos:related</code>, declared in a small extension schema. Labels are given in English, in Sanskrit in Devanagari script and in IAST transliteration, with epithets as alternative labels and common spellings as hidden labels. Every character with an English Wikipedia article is mapped to its Wikidata item and DBpedia resource. A SHACL [SHACL] shapes file states the SKOS integrity conditions and the conventions of the scheme.</p>
<p>The content follows the Wikipedia article <i>Mahabharata</i> [WIKIPEDIA] and the character articles it links to. The scheme holds {len(ctx.chars)} characters under {len(ctx.groups)} groupings, with {len(ctx.colls)} collections that cut across the hierarchy.</p>""")


def scope_body(ctx: Ctx) -> str:
    return cites(f"""<p>The scheme covers the characters named in the synopsis of the Wikipedia article and the principal figures of the Kurukshetra war: {len(ctx.chars)} characters. The epic names many hundreds more (the Kauravas alone are a hundred brothers); the Wikipedia list of characters [WIKIPEDIA-LIST] is the natural source for additions. In scope are the characters of the Mahabharata proper, including its frame story and the deities who act in it. Out of scope are characters who appear only in the Ramopakhyana retelling of the Ramayana, and figures from regional retellings.</p>
<p>Parentage, deaths and the days on which warriors fell follow the Wikipedia articles, which follow the Critical Edition of the Bhandarkar Oriental Research Institute and note the variants. Where recensions differ, the commonly cited reading is used. Devanagari and IAST forms follow standard dictionary practice. The descriptions paraphrase the articles, which are published under CC BY-SA 4.0; the same licence applies to the scheme (<a href="#sources">Sources, licence and citation</a>).</p>""")


def namespaces_body(ctx: Ctx) -> str:
    bound = dict(ctx.g.namespaces()) | dict(ctx.sg.namespaces())
    for prefix, ns, _ in PREFIXES:
        if str(bound.get(prefix, "")) != ns:
            raise SystemExit(f"render_site: prefix {prefix}: is bound to {bound.get(prefix)} in the data, not {ns}")
    rows = [[code(p + ":"), a(ns, esc(ns)) if ns.startswith("http") else esc(ns), cites(esc(use))]
            for p, ns, use in PREFIXES]
    return ("<p>This document and the data use the following prefixes. The first four namespaces belong to the scheme "
            "and resolve to this document (<a href=\"#reading\">How to read this document</a>); the others are the "
            "vocabularies it reuses.</p>" + simple_table(["Prefix", "Namespace IRI", "Used for"], rows))


def reading_body(ctx: Ctx) -> str:
    legend = "".join(f'<li><span class="swatch {k.lower()}"></span>{k}</li>'
                     for k in ("Scheme", "Class", "Property", "Grouping", "Character", "Collection", "Shape"))
    return cites(f"""<p>The sections up to <a href="#collections">Collections</a> describe the scheme; the cross-reference sections hold one <b>entry</b> per term. An entry is a table headed by the kind of term, its English label and its prefixed name. The colour of the band says what kind of term it is:</p>
<ul class="legend">{legend}</ul>
<p><b>Names.</b> Terms are written with the prefixes of the namespace table: <code>mbh:arjuna</code> is the concept Arjuna, <code>mbhx:childOf</code> a property of the schema. Every prefixed name in this document links to the entry of its term; a term of another vocabulary links to its own IRI.</p>
<p><b>IRIs resolve here.</b> The IRI of a term is the first row of its entry. The scheme uses hash IRIs built on three namespace documents served beside this page: <a href="characters.html"><code>/characters</code></a> for concepts and collections, <a href="schema.html"><code>/schema</code></a> for classes and properties and <a href="shapes.html"><code>/shapes</code></a> for the SHACL shapes. Each lists its terms and forwards a browser to the entry here that the fragment names, so <code>{esc(str(MBH))}arjuna</code> opens the entry for Arjuna. The site does not negotiate content: the Turtle is at fixed addresses (<a href="#access">Access and use</a>).</p>
<p><b>Relations are stated once.</b> The data writes each relation in the direction its property names: <code>mbhx:childOf</code> on the child, <code>mbhx:killedBy</code> on the one killed, <code>mbhx:studentOf</code> on the student. An entry shows those statements under the label of the property, and the other direction under the label of the declared inverse (<i>parent of</i>, <i>killed</i>, <i>teacher of</i>), marked <span class="inf">inferred</span>, computed from the statements in the data. Symmetric relations (<i>spouse of</i>, <i>sibling of</i>, <i>friend of</i>, <i>rival of</i>) are stated once per pair and shown on both.</p>
<p><b>Languages.</b> Labels carry language tags [BCP47]: <span class="lt">en</span> English, <span class="lt">sa-Deva</span> Sanskrit in Devanagari script, <span class="lt">sa-Latn</span> Sanskrit in IAST transliteration.</p>
<p><b>Counts.</b> Every number in this document is computed from the data when the page is generated. The count after a grouping is the number of characters placed under it or under its narrower groupings; a character under two groupings is counted under both.</p>""")


def model_figure(ctx: Ctx) -> str:
    g = ctx.g
    cg = sum(1 for c in ctx.chars for _ in g.objects(c, SKOS.broader))
    gg = sum(1 for gr in ctx.groups for _ in g.objects(gr, SKOS.broader))
    rel = sum(ctx.count(p) for p in ctx.stated)
    cm = sum(1 for c in ctx.chars for p in (SKOS.exactMatch, SKOS.closeMatch) for _ in g.objects(c, p))
    gm = sum(1 for gr in ctx.groups for p in (SKOS.exactMatch, SKOS.closeMatch) for _ in g.objects(gr, p))
    cw = sum(1 for c in ctx.chars for _ in g.objects(c, FOAF.isPrimaryTopicOf))
    gw = sum(1 for gr in ctx.groups for _ in g.objects(gr, FOAF.isPrimaryTopicOf))

    def box(x, y, w, h, href, lines, cls=""):
        texts = "".join(f'<text x="{x + w // 2}" y="{y + 21 + i * 16}" class="{"t1" if i == 0 else "t2"}">{esc(t)}</text>'
                        for i, t in enumerate(lines))
        inner = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4"/>{texts}'
        return f'<g class="box {cls}">' + (f'<a href="{href}">{inner}</a>' if href else inner) + "</g>"

    def edge(d, cls=""):
        return f'<path class="edge {cls}" d="{d}"/>'

    def label(x, y, text, anchor_="middle"):
        return f'<text class="lbl" x="{x}" y="{y}" text-anchor="{anchor_}">{esc(text)}</text>'

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 440" role="img" aria-labelledby="figure-model-title">',
        '<title id="figure-model-title">The model of the scheme</title>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#444"/></marker></defs>',
        box(360, 20, 240, 60, "#characters", ["skos:ConceptScheme", "mb:characters"]),
        box(60, 180, 240, 72, "#Grouping", ["mbhx:Grouping", f"{len(ctx.groups)} groupings, {len(ctx.tops)} top concepts",
                                             "lineage · generation · royal house · class of being"]),
        box(420, 110, 120, 40, "", ["skos:Concept"], "ext"),
        box(660, 180, 240, 72, "#Character", ["mbhx:Character", f"{len(ctx.chars)} characters",
                                              f"mbhx:fellOnWarDay → xsd:integer ({ctx.count(MBHX.fellOnWarDay)})"]),
        box(660, 360, 240, 60, "#crossref-collections", ["skos:Collection · skos:OrderedCollection",
                                                          f"{len(ctx.colls)} collections, {len(ctx.ordered)} ordered"]),
        box(60, 360, 240, 60, "", ["Wikidata · DBpedia · Wikipedia", "external resources"], "ext"),
        edge("M 240 180 L 400 80"), label(300, 118, f"skos:topConceptOf ({len(ctx.tops)})", "end"),
        edge("M 660 216 L 300 216"), label(480, 206, f"skos:broader ({cg})"),
        edge("M 110 180 C 70 110, 190 110, 150 180"), label(130, 104, f"skos:broader ({gg})"),
        edge("M 710 180 C 670 110, 790 110, 750 180"),
        label(730, 92, "mbhx:childOf · spouseOf · killedBy · studentOf …"),
        label(730, 106, f"{len(ctx.stated)} sub-properties of skos:related, {rel} statements"),
        edge("M 300 186 L 420 142", "dashed"), edge("M 660 186 L 540 142", "dashed"),
        label(480, 166, "rdfs:subClassOf (disjoint classes)"),
        edge("M 780 360 L 780 252"), label(790, 310, f"skos:member ({ctx.count(SKOS.member)})", "start"),
        edge("M 660 252 L 300 360"), label(480, 290, f"skos:exactMatch · closeMatch ({cm}) · foaf:isPrimaryTopicOf ({cw})"),
        edge("M 180 252 L 180 360"), label(190, 310, f"skos:closeMatch · exactMatch ({gm})", "start"),
        label(190, 324, f"foaf:isPrimaryTopicOf ({gw})", "start"),
        "</svg>",
    ]
    caption = ("<figcaption><b>Figure 1.</b> The model. Boxes are classes, arrows are properties with the number of "
               "statements in the data; a box links to its entry. Groupings form the hierarchy and characters hang "
               "from them; kinship and narrative relations connect characters to each other; collections cut across "
               "the hierarchy; mappings anchor concepts outside the scheme.</figcaption>")
    return f'<figure id="{ctx.uid("figure-model")}">{"".join(parts)}{caption}</figure>'


def glance_body(ctx: Ctx) -> str:
    return model_figure(ctx) + f"""<p>The scheme has two kinds of concept. A {code_link(ctx, MBHX.Character)} is a person, deity or other being that acts or is named in the epic. A {code_link(ctx, MBHX.Grouping)} is a lineage, generation, royal house, order or class of being under which characters are placed. Both are subclasses of <code>skos:Concept</code>, and they are disjoint.</p>
<p><code>skos:broader</code> runs from a character to its groupings and from a grouping to a wider grouping. A character is never broader than another character: the hierarchy is a classification, not a genealogy. Family ties are expressed as relations instead, so <code>skos:broader+</code> always means <i>belongs to</i> and <code>mbhx:childOf+</code> always means <i>descends from</i>.</p>"""


def classes_table(ctx: Ctx) -> str:
    g, rows = ctx.g, []
    for cls in ctx.classes:
        rows.append([code_link(ctx, cls), str(sum(1 for _ in g.subjects(RDF.type, cls))),
                     esc(lit1(g, cls, SKOS.definition) or "")])
    rows.append([code_link(ctx, SKOS.ConceptScheme), "1", f"The scheme itself, {code_link(ctx, SCHEME)}."])
    rows.append([code_link(ctx, SKOS.Collection), str(len(ctx.colls) - len(ctx.ordered)),
                 f'Cross-cutting groups of characters (<a href="#collections">Collections</a>).'])
    rows.append([code_link(ctx, SKOS.OrderedCollection), str(len(ctx.ordered)),
                 "Groups whose order carries meaning: birth order, the sequence of commanders."])
    return ("<p>The two classes of the extension schema and the SKOS classes the scheme instantiates.</p>"
            + simple_table(["Class", "Instances", "Meaning"], rows))


def properties_body(ctx: Ctx) -> str:
    g, rows = ctx.g, []
    for p in ctx.stated:
        inverse = "symmetric" if p in ctx.symmetric else code_link(ctx, ctx.inverse[p])
        rows.append((ctx.count(p), code_link(ctx, p), inverse, esc(lit1(g, p, SKOS.definition) or "")))
    rows.sort(key=lambda r: (-r[0], r[1]))
    table = [[r[1], r[2], str(r[0]), r[3]] for r in rows]
    table.append([code_link(ctx, MBHX.fellOnWarDay), f"range {code('xsd:integer')}, 1 to 18",
                  str(ctx.count(MBHX.fellOnWarDay)), esc(lit1(g, MBHX.fellOnWarDay, SKOS.definition) or "")])
    return cites(f"""<p>Relations between characters are sub-properties of <code>skos:related</code>, declared in the extension schema ({code_link(ctx, ONTOLOGY)}). Specialising SKOS this way is the pattern of the SKOS Primer, section 4.7 [SKOS-PRIMER]: every <code>mbhx:killedBy</code> statement is also a <code>skos:related</code> statement for a tool that knows only SKOS, and a tool that knows the schema gets the finer meaning. Each relation is stated once, in the direction the property names; the inverse is declared with <code>owl:inverseOf</code> and left to inference. One datatype property records the day of the Kurukshetra war on which a character fell.</p>"""
                 + simple_table(["Property", "Inverse or range", "Stated", "Meaning"], table))


def labels_body(ctx: Ctx) -> str:
    g, b = ctx.g, MBH["bhishma"]
    rows = [[code("skos:prefLabel"), "en, sa-Deva, sa-Latn",
             "One name per language. English labels are unique across the scheme. Sanskrit uses the dictionary stem "
             "(<i>Aśvatthāman</i>, <i>Bhūriśravas</i>); the familiar nominative (<i>Aśvatthāmā</i>) is an alternative label."],
            [code("skos:altLabel"), "en, sa-Deva, sa-Latn",
             "Epithets, patronymics and matronymics (<i>Partha</i>, <i>Radheya</i>, <i>Saubala</i>), and the names taken "
             "in disguise at Virata's court (<i>Brihannala</i>, <i>Kanka</i>, <i>Sairandhri</i>)."],
            [code("skos:hiddenLabel"), "en",
             "Common English spellings for search (<i>Bheem</i>, <i>Dhritrashtra</i>, <i>Yudhisthir</i>). Not meant for display."]]
    example = [["Preferred", labels_cell(g, b, SKOS.prefLabel)], ["Alternative", labels_cell(g, b, SKOS.altLabel)],
               ["Hidden", labels_cell(g, b, SKOS.hiddenLabel)]]
    return (simple_table(["Property", "Languages", "Holds"], rows)
            + f"<p>{term_link(ctx, b)}, for example:</p>" + simple_table(["Label", "Values"], example)
            + "<p>Characters who share a name are told apart in the label itself: <i>Chitrangada (son of Shantanu)</i> and "
              "<i>Chitrangada (princess of Manipura)</i>; <i>Uttara (prince of Matsya)</i> and <i>Uttara (princess of Matsya)</i>; "
              "<i>Radha (foster mother of Karna)</i>. Each carries a <code>skos:scopeNote</code> pointing to the other.</p>")


def vocabulary_body(ctx: Ctx) -> str:
    counts = Counter(p for _, p, _ in ctx.g)
    rows = [[code_link(ctx, p), str(n)] for p, n in sorted(counts.items(), key=lambda kv: (-kv[1], qname(kv[0])))]
    return (f"<p>Every property that occurs in the data, with the number of statements that use it ({len(ctx.g):,} "
            "statements in all). <code>rdf:first</code> and <code>rdf:rest</code> build the member lists of the "
            "ordered collections.</p>" + simple_table(["Property", "Statements"], rows))


def counts_body(ctx: Ctx) -> str:
    g = ctx.g
    pref = Counter(o.language for o in g.objects(None, SKOS.prefLabel))
    poly = [c for c in ctx.chars if sum(1 for _ in g.objects(c, SKOS.broader)) > 1]
    wd_mapped = [c for c in ctx.chars if any(str(o).startswith(WD)
                                            for p in (SKOS.exactMatch, SKOS.closeMatch) for o in g.objects(c, p))]
    wp = [c for c in ctx.chars if (c, FOAF.isPrimaryTopicOf, None) in g]
    unmapped = [c for c in ctx.chars if c not in wd_mapped]
    rows = [["Triples", f"{len(g):,}"],
            [f"Characters ({code_link(ctx, MBHX.Character)})", str(len(ctx.chars))],
            [f"Groupings ({code_link(ctx, MBHX.Grouping)})", f"{len(ctx.groups)}, of which {len(ctx.tops)} top concepts"],
            ["Collections", f"{len(ctx.colls)}, of which {len(ctx.ordered)} ordered"],
            ["Preferred labels", f"{sum(pref.values())} (en {pref.get('en', 0)} · sa-Deva {pref.get('sa-Deva', 0)} · "
                                 f"sa-Latn {pref.get('sa-Latn', 0)})"],
            ["Alternative labels (epithets, patronymics, names in disguise)", str(ctx.count(SKOS.altLabel))],
            ["Hidden labels (spelling variants)", str(ctx.count(SKOS.hiddenLabel))],
            ["Relations between characters", f"{sum(ctx.count(p) for p in ctx.stated)} statements over "
                                             f"{len(ctx.stated)} properties"],
            ["Characters with a day of the war on which they fell", str(ctx.count(MBHX.fellOnWarDay))],
            ["Characters under more than one grouping", f"{len(poly)}: {name_list(ctx, poly)}"],
            ["Characters mapped to Wikidata", f"{len(wd_mapped)} of {len(ctx.chars)}"],
            ["Characters linked to their Wikipedia article", f"{len(wp)} of {len(ctx.chars)}"]]
    text = simple_table(["Measure", "Value"], rows)
    if unmapped:
        text += ("<p>Characters without a Wikidata item of their own, linked to the Wikipedia list article instead: "
                 + name_list(ctx, unmapped) + ".</p>")
    return text


def top_concepts_table(ctx: Ctx) -> str:
    rows, total = [], 0
    for t in ctx.tops:
        n = len(ctx.below(t))
        total += n
        rows.append([term_link(ctx, t), esc(lit1(ctx.g, t, SKOS.prefLabel, "sa-Latn") or ""),
                     esc(lit1(ctx.g, t, SKOS.definition) or ""), str(n)])
    note = (f"<p>The character column sums to {total} for {len(ctx.chars)} characters because {total - len(ctx.chars)} "
            "placements are second placements of characters that belong to two groupings.</p>")
    return simple_table(["Top concept", "Sanskrit", "Covers", "Characters"], rows) + note


def tree(ctx: Ctx) -> str:
    g = ctx.g

    def character_item(c, here):
        bits = [term_link(ctx, c) + sanskrit(g, c)]
        others = [term_link(ctx, o) for o in ctx.sorted(g.objects(c, SKOS.broader)) if o != here]
        if others:
            bits.append('<span class="also">also under ' + ", ".join(others) + "</span>")
        return f'<li class="character">{" ".join(bits)}</li>'

    def walk(node):
        sa = lit1(g, node, SKOS.prefLabel, "sa-Latn")
        head = (term_link(ctx, node) + (f' <span class="sa">{esc(sa)}</span>' if sa else "")
                + f' <span class="count">{len(ctx.below(node))}</span>')
        children = ctx.sorted(g.subjects(SKOS.broader, node))
        inner = "".join(walk(ch) for ch in children if ch in ctx.groups)
        inner += "".join(character_item(ch, node) for ch in children if ch in ctx.chars)
        return f'<li class="grouping">{head}<ul>{inner}</ul></li>'

    return '<ul class="tree">' + "".join(walk(t) for t in ctx.tops) + "</ul>"


def hierarchy_body(ctx: Ctx) -> str:
    return (f"<p>The {len(ctx.tops)} top concepts of the scheme, with the number of characters each one covers.</p>"
            + top_concepts_table(ctx)
            + "<p>Every concept in its place under <code>skos:broader</code>. Groupings are in bold with the number of "
              "characters below them; characters show their Devanagari and IAST labels. A character that belongs to two "
              "groupings is listed under both, with a pointer to the other.</p>" + tree(ctx))


def collections_body(ctx: Ctx) -> str:
    rows = [[term_link(ctx, c), "ordered" if c in ctx.ordered else "", str(sum(1 for _ in ctx.g.objects(c, SKOS.member))),
             esc(lit1(ctx.g, c, SKOS.definition) or "")] for c in ctx.colls]
    return ("<p>Collections gather characters across the hierarchy. An ordered collection is used where the order "
            "carries meaning; it states both <code>skos:memberList</code> and <code>skos:member</code>, so that a "
            "consumer without SKOS inference still sees the membership. Each collection has an entry in "
            "<a href=\"#crossref-collections\">Cross-reference for collections</a>.</p>"
            + simple_table(["Collection", "Kind", "Members", "Definition"], rows))


def schema_body(ctx: Ctx) -> str:
    return cites("<p>The extension schema is an OWL 2 ontology [OWL2-OVERVIEW] of two classes, one datatype property "
                 "and the relation properties, all declared in the data file itself. Relation properties are "
                 "sub-properties of <code>mbhx:characterRelation</code>, which is a sub-property of "
                 "<code>skos:related</code>; each is paired with a declared inverse or is itself symmetric. "
                 "<code>skos:related</code> is symmetric, but that places no restriction on its sub-properties "
                 "(SKOS Reference, section 8.6.3 [SKOS-REFERENCE]).</p>") + ontology_entry(ctx)


def groupings_body(ctx: Ctx) -> str:
    return (f"<p>The {len(ctx.groups)} groupings in the order of the hierarchy: each top concept followed by the "
            "groupings below it.</p>" + "\n".join(grouping_entry(ctx, gr) for gr in ctx.groups))


def characters_body(ctx: Ctx) -> str:
    chars = ctx.by_label(ctx.chars)
    letters = sorted({en(ctx.g, c)[0].upper() for c in chars})
    out = [f"<p>The {len(chars)} characters in alphabetical order of their English preferred label.</p>",
           '<p class="letters">' + " ".join(a(f"#characters-{x}", x) for x in letters) + "</p>"]
    current = None
    for c in chars:
        x = en(ctx.g, c)[0].upper()
        if x != current:
            current = x
            out.append(f'<div class="letter" id="{ctx.uid("characters-" + x)}">{x}</div>')
        out.append(character_entry(ctx, c))
    return "\n".join(out)


def validation_body(ctx: Ctx) -> str:
    layers = [["SKOS integrity conditions (S9, S13, S14, S19, S27, S36, S37, S46 of the SKOS Reference)",
               "At most one <code>prefLabel</code> per language; <code>prefLabel</code>, <code>altLabel</code> and "
               "<code>hiddenLabel</code> pairwise disjoint; a concept is neither a scheme nor a collection; "
               "<code>broader</code> points at concepts; <code>related</code> is disjoint with the transitive hierarchy; "
               "an ordered collection has exactly one well-formed member list that agrees with <code>skos:member</code>; "
               "<code>exactMatch</code> is disjoint with <code>broadMatch</code> and <code>relatedMatch</code>."],
              ["Conventions of this scheme",
               "Every concept has an English preferred label and definition and is in the scheme; it is a top concept "
               "or has a broader concept, never both; a character sits under groupings only and is never a top concept; "
               "a grouping has narrower concepts and carries no character relations; relations connect characters to "
               "characters, in one direction only, symmetric ones once per pair, with no self-relations and no "
               "parent-child cycles; mapping IRIs match the Wikidata, DBpedia and Wikipedia patterns; every character "
               "has an external anchor; <code>fellOnWarDay</code> is an integer from 1 to 18."]]
    return cites(f"""<p>The shapes in <a href="shapes.ttl">shapes.ttl</a> ({len(ctx.sg):,} triples, {len(ctx.shapes)} node shapes) state what the data must satisfy, in SHACL [SHACL]. <code>scripts/validate.py</code> runs them with pySHACL under RDFS inference, so that sub-properties and subclasses count, then checks that every <code>mbh:</code> IRI used in the data is also declared. Continuous integration runs the validator on every push and fails on any violation.</p>
<pre>pip install -r requirements.txt
python scripts/validate.py</pre>
<p>The shapes have two layers:</p>""") + simple_table(["Layer", "What is checked"], layers)


PYTHON_EXAMPLE = f'''from rdflib import Graph, Namespace
from rdflib.collection import Collection
from rdflib.namespace import SKOS

g = Graph().parse("{SITE_URL}mahabharata_characters.ttl")
MBH = Namespace("{MBH}")
MBHX = Namespace("{MBHX}")

def label(node, lang="en"):
    return next(str(l) for l in g.objects(node, SKOS.prefLabel) if l.language == lang)

# Relations are stated in one direction: killedBy on the one who was killed.
print(sorted(label(c) for c in g.subjects(MBHX.killedBy, MBH.bhima)))

# Walk up the hierarchy.
print([label(b) for b in g.transitive_objects(MBH.draupadi, SKOS.broader) if b != MBH.draupadi])

# Read an ordered collection in order.
head = g.value(MBH["coll-kaurava-commanders"], SKOS.memberList)
print([label(m) for m in Collection(g, head)])
'''


def access_body(ctx: Ctx) -> str:
    return cites(f"""<p>The scheme is one RDF 1.1 Turtle file, <a href="mahabharata_characters.ttl">mahabharata_characters.ttl</a> ({len(ctx.g):,} triples); the shapes are <a href="shapes.ttl">shapes.ttl</a>. Both are served beside this page and declared as <code>rel="alternate"</code> links in its head. The site does not negotiate content: a request for a namespace IRI returns HTML, and the Turtle is fetched from these two addresses. The repository's <code>scripts/export.py</code> writes RDF/XML, JSON-LD and N-Triples copies for tools that want them.</p>
<p>The file is plain Turtle, so it opens in Protégé, TopBraid Composer, Skosmos (through a SPARQL endpoint such as Fuseki) and any RDF library. With Apache Jena, <code>riot --validate mahabharata_characters.ttl</code> checks the syntax and <code>arq --data=mahabharata_characters.ttl --query=q.rq</code> runs a query. With rdflib:</p>
<pre class="python">{esc(PYTHON_EXAMPLE)}</pre>""")


def query_results(ctx: Ctx, body: str) -> str:
    res = ctx.g.query(SPARQL_PREFIXES + body)
    headers = [str(v) for v in res.vars]
    rows = []
    for row in res:
        bound = row.asdict()
        cells = []
        for v in res.vars:
            val = bound.get(str(v))
            if val is None:
                cells.append("")
            elif isinstance(val, URIRef):
                cells.append(code_link(ctx, val) if is_internal(val) else a(str(val), esc(qname(val))))
            else:
                cells.append(esc(str(val)))
        rows.append(cells)
    if not rows:
        return "<p><i>No results.</i></p>"
    if len(headers) == 1:
        return f"<p>{len(rows)} result{'s' if len(rows) != 1 else ''}: " + ", ".join(r[0] for r in rows) + ".</p>"
    return simple_table([esc(h) for h in headers], rows)


def queries_body(ctx: Ctx) -> str:
    out = [cites("<p>Each query was run against the data with rdflib when this page was generated, and the result "
                 "shown is what it returned. The queries are SPARQL 1.1 [SPARQL11-QUERY] with the prefixes of "
                 "<a href=\"#namespaces\">Namespaces</a>. None needs inference: where the inverse of a relation is "
                 "wanted, the query uses an inverse property path.</p>")]
    for i, (title, explanation, body) in enumerate(QUERIES, 1):
        out.append(f'<h4 id="{ctx.uid(f"query-{i}")}">{i}. {esc(title)}</h4><p>{inline_md(explanation)}</p>'
                   f'<pre class="sparql">{esc(body)}</pre>{query_results(ctx, body)}')
    return "\n".join(out)


def sources_body(ctx: Ctx) -> str:
    g, s = ctx.g, SCHEME
    version = str(g.value(s, OWL.versionInfo))
    year = str(g.value(s, DCTERMS.created))[:4]
    bibtex = ("@misc{aggarwal" + year + "mahabharata,\n  author  = {Aggarwal, Tanay},\n"
              "  title   = {Characters of the {Mahabharata}: a {SKOS} concept scheme},\n"
              f"  year    = {{{year}}},\n  version = {{{version}}},\n  url     = {{{SITE_URL}}},\n"
              "  note    = {RDF Turtle dataset, CC BY-SA 4.0}\n}")
    return cites(f"""<p><b>Sources.</b> {url_list(g, s, DCTERMS.source)} on English Wikipedia [WIKIPEDIA] [WIKIPEDIA-LIST], the character articles linked from them, and Wikidata [WIKIDATA] for identifiers. {esc(lit1(g, s, RDFS.comment) or "")}</p>
<p><b>Licence.</b> The concept scheme, the shapes and this document are released under {a("https://creativecommons.org/licenses/by-sa/4.0/", "Creative Commons Attribution-ShareAlike 4.0 International")}. The descriptions paraphrase English Wikipedia, whose text is published under CC BY-SA 4.0, so the same licence applies here. The scripts that generate this document are released under the MIT License. When you reuse the data, credit <i>Characters of the Mahabharata: a SKOS concept scheme</i> and Wikipedia, and link to the licence.</p>
<p><b>Citation.</b> Author: {esc(AUTHOR)}. Cite the scheme as:</p>
<blockquote>Aggarwal, Tanay. <i>Characters of the Mahabharata: a SKOS concept scheme</i>, version {esc(version)}. RDF Turtle dataset, {year}. CC BY-SA 4.0. {a(SITE_URL, esc(SITE_URL))}</blockquote>
<pre class="bibtex">{esc(bibtex)}</pre>""")


def references_body(ctx: Ctx) -> str:
    items = "".join(f'<dt id="{ctx.uid("bib-" + key)}">[{esc(key)}]</dt>'
                    f'<dd><cite>{esc(title)}</cite>. {esc(details)} {a(url, esc(url))}</dd>'
                    for key, title, details, url in REFERENCES)
    return f'<dl class="refs">{items}</dl>'


def changes_body(ctx: Ctx) -> str:
    g, s = ctx.g, SCHEME
    modified = g.value(s, DCTERMS.modified) or g.value(s, DCTERMS.created)
    changelog = f"{REPO_URL}/blob/main/CHANGELOG.md" if REPO_URL else "CHANGELOG.md"
    return (f"<p>Version {code(g.value(s, OWL.versionInfo))}, created {esc(long_date(str(g.value(s, DCTERMS.created))))}; "
            f"the data was last modified on {esc(long_date(str(modified)))}. This is the first release. The version is "
            f"carried in the data as <code>owl:versionInfo</code> on {code_link(ctx, SCHEME)} and {code_link(ctx, ONTOLOGY)}; "
            f"the full history is in {a(changelog, 'CHANGELOG.md')}.</p>")


# --------------------------------------------------------------------------- page

CSS = """
html { background: #fff; }
body { margin: 0 auto; padding: 1.5em 2em 4em; max-width: 64em; color: #1a1a1a; line-height: 1.5; font-size: 16px;
  font-family: "Helvetica Neue", Helvetica, Arial, "Noto Sans", "Noto Sans Devanagari", sans-serif; }
a { color: #0645ad; text-decoration: none; } a:hover { text-decoration: underline; } a:visited { color: #5a3e99; }
h1, h2, h3 { color: #005a9c; font-weight: 600; line-height: 1.25; text-align: left; }
h1 { font-size: 2em; margin: 0.6em 0 0.2em; }
h2 { font-size: 1.5em; margin-top: 2.2em; padding-bottom: 0.2em; border-bottom: 1px solid #d0d7de; }
h3 { font-size: 1.2em; margin-top: 1.8em; }
h4 { font-size: 1em; margin: 1.6em 0 0.4em; }
.secno { color: #005a9c; margin-right: 0.35em; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.92em; }
pre { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 4px; padding: 0.8em 1em; overflow-x: auto;
  line-height: 1.4; }
blockquote { margin: 1em 0; padding: 0.6em 1em; border-left: 4px solid #d0d7de; }
hr { border: 0; border-top: 1px solid #d0d7de; margin: 1.5em 0; }
.head .badge { display: inline-block; margin-top: 1.5em; padding: 0.1em 0.6em; font-size: 0.8em; letter-spacing: 0.08em;
  text-transform: uppercase; color: #005a9c; border: 1px solid #005a9c; border-radius: 3px; }
.head h2 { margin: 0.2em 0 1em; border: 0; color: #1a1a1a; font-size: 1.15em; font-weight: normal; }
.head dl { display: grid; grid-template-columns: max-content 1fr; gap: 0.25em 1.2em; margin: 1em 0; }
.head dt { font-weight: 600; } .head dd { margin: 0; }
ol.toc, ol.toc ol { list-style: none; padding-left: 0; } ol.toc ol { padding-left: 1.6em; } ol.toc li { margin: 0.15em 0; }
table { width: 100%; margin: 1em 0; border-collapse: collapse; font-size: 0.95em; }
table.simple th { padding: 0.4em 0.6em; background: #005a9c; color: #fff; text-align: left; }
table.simple td { padding: 0.4em 0.6em; border-bottom: 1px solid #d0d7de; vertical-align: top; }
table.simple tr:nth-child(even) td { background: #f6f8fa; }
.term { margin: 1.4em 0; border: 1px solid #d0d7de; border-left: 5px solid var(--c, #005a9c); border-radius: 4px; }
.term h4 { margin: 0; padding: 0.5em 0.8em; background: var(--bg, #eef3f8); border-bottom: 1px solid #d0d7de; }
.term .kind { margin-right: 0.6em; font-size: 0.75em; letter-spacing: 0.06em; text-transform: uppercase; color: #444; }
.term .lbl { font-size: 1.1em; }
.term .qn, .term .sa { margin-left: 0.6em; font-weight: normal; color: #444; }
.term .self { float: right; color: #999; font-weight: normal; }
table.definition { margin: 0; }
table.definition th { width: 11em; padding: 0.35em 0.8em; text-align: left; font-weight: 600; color: #444;
  vertical-align: top; border-top: 1px solid #eee; }
table.definition td { padding: 0.35em 0.8em; vertical-align: top; border-top: 1px solid #eee; }
table.definition tr:first-child th, table.definition tr:first-child td { border-top: 0; }
table.definition ol, table.definition ul { margin: 0; padding-left: 1.4em; }
.scheme, .ontology { --c: #005a9c; --bg: #e6eef7; } .class { --c: #1565c0; --bg: #e3f2fd; }
.property { --c: #6a1b9a; --bg: #f3e5f5; } .grouping { --c: #2e7d32; --bg: #e8f5e9; }
.character { --c: #d4a017; --bg: #fff8e1; } .collection { --c: #00796b; --bg: #e0f2f1; }
.shape, .shapes { --c: #546e7a; --bg: #eceff1; }
"""
CSS += """
ul.legend { list-style: none; padding: 0; } ul.legend li { display: inline-block; margin: 0 1.2em 0.3em 0; }
.swatch { display: inline-block; width: 1em; height: 1em; margin-right: 0.4em; vertical-align: -0.15em;
  background: var(--bg); border-left: 4px solid var(--c); border-radius: 2px; }
.lt { display: inline-block; margin-right: 0.35em; padding: 0 0.35em; font-family: monospace; font-size: 0.72em;
  color: #555; background: #f1f3f4; border-radius: 3px; vertical-align: 0.1em; }
.inf { font-weight: normal; font-size: 0.8em; font-style: italic; color: #777; }
.msg { font-style: italic; color: #555; }
.turtle { white-space: nowrap; }
ul.tree, ul.tree ul { list-style: none; padding-left: 1.4em; border-left: 1px dotted #bbb; }
ul.tree { padding-left: 0; border: 0; } ul.tree li { margin: 0.15em 0; } ul.tree li.grouping > a { font-weight: 600; }
.count { font-size: 0.85em; color: #777; } .sa { color: #555; } .also { font-size: 0.85em; font-style: italic; color: #777; }
.letters { line-height: 2; } .letters a { display: inline-block; min-width: 1.6em; margin: 0 0.1em; text-align: center;
  border: 1px solid #d0d7de; border-radius: 3px; }
.letter { margin: 2em 0 0; font-size: 1.4em; font-weight: 600; color: #005a9c; border-bottom: 2px solid #005a9c; }
figure { margin: 1.5em 0; } figure svg { width: 100%; height: auto; }
figcaption { margin-top: 0.4em; font-size: 0.9em; color: #444; }
svg .box rect { fill: #fff; stroke: #005a9c; stroke-width: 1.5; } svg .box.ext rect { stroke: #777; stroke-dasharray: 5 4; }
svg .box text { font-size: 12px; fill: #1a1a1a; text-anchor: middle; }
svg .box .t1 { font-size: 13px; font-weight: 600; fill: #005a9c; } svg .box .t2 { font-size: 11px; fill: #444; }
svg .edge { fill: none; stroke: #444; stroke-width: 1.3; marker-end: url(#arrow); } svg .edge.dashed { stroke-dasharray: 5 4; }
svg .lbl { font-size: 11px; fill: #333; paint-order: stroke; stroke: #fff; stroke-width: 4px; stroke-linejoin: round; }
dl.refs dt { margin-top: 0.6em; font-weight: 600; } dl.refs dd { margin: 0 0 0 2em; }
footer { margin-top: 3em; padding-top: 1em; font-size: 0.85em; color: #666; border-top: 1px solid #d0d7de; }
@media (max-width: 40em) { body { padding: 1em; } table.definition th { width: 7em; } .head dl { display: block; } }
"""


def html_page(title: str, description: str, body: str, extra_head: str = "") -> str:
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8"/>\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"/>\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(description)}"/>\n'
            f'<link rel="alternate" type="text/turtle" href="mahabharata_characters.ttl" title="The concept scheme (RDF Turtle)"/>\n'
            f'<link rel="alternate" type="text/turtle" href="shapes.ttl" title="SHACL shapes (RDF Turtle)"/>\n'
            f'<link rel="license" href="https://creativecommons.org/licenses/by-sa/4.0/"/>\n'
            f'{extra_head}<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n')


def jsonld(ctx: Ctx, title: str, abstract: str, version: str, created: str, modified: str) -> str:
    data = {"@context": "https://schema.org", "@type": "Dataset", "name": f"{title}: a SKOS concept scheme",
            "description": abstract, "url": SITE_URL, "version": version, "dateCreated": created,
            "dateModified": modified, "license": "https://creativecommons.org/licenses/by-sa/4.0/",
            "creator": {"@type": "Person", "name": AUTHOR}, "inLanguage": ["en", "sa"],
            "keywords": ["SKOS", "Mahabharata", "knowledge organization system", "linked data", "SHACL"],
            "isBasedOn": [str(s) for s in sorted(ctx.g.objects(SCHEME, DCTERMS.source), key=str)],
            "distribution": [{"@type": "DataDownload", "encodingFormat": "text/turtle",
                              "contentUrl": SITE_URL + "mahabharata_characters.ttl"}]}
    text = json.dumps(data, ensure_ascii=False, indent=1).replace("<", "\\u003c").replace("&", "\\u0026")
    return f'<script type="application/ld+json">\n{text}\n</script>\n'


def spec_page(ctx: Ctx) -> str:
    g = ctx.g
    version = str(g.value(SCHEME, OWL.versionInfo))
    created = str(g.value(SCHEME, DCTERMS.created))
    modified = str(g.value(SCHEME, DCTERMS.modified) or g.value(SCHEME, DCTERMS.created))
    title = str(g.value(SCHEME, DCTERMS.title))
    abstract = str(g.value(SCHEME, DCTERMS.description))
    sections = [
        Section("introduction", "Introduction", intro_body(ctx), [
            Section("scope", "Scope and sources", scope_body(ctx)),
            Section("namespaces", "Namespaces", namespaces_body(ctx)),
            Section("reading", "How to read this document", reading_body(ctx))]),
        Section("at-a-glance", "The scheme at a glance", glance_body(ctx), [
            Section("classes", "Classes", classes_table(ctx)),
            Section("properties", "Properties", properties_body(ctx)),
            Section("labels", "Labels", labels_body(ctx)),
            Section("vocabulary", "Vocabulary used", vocabulary_body(ctx)),
            Section("counts", "Counts", counts_body(ctx))]),
        Section("hierarchy", "The hierarchy", hierarchy_body(ctx)),
        Section("collections", "Collections", collections_body(ctx)),
        Section("crossref-scheme", "The concept scheme", scheme_entry(ctx)),
        Section("crossref-schema", "Cross-reference for the schema", schema_body(ctx), [
            Section("crossref-classes", "Classes", "\n".join(class_entry(ctx, c) for c in ctx.classes)),
            Section("crossref-properties", "Properties", "\n".join(property_entry(ctx, p) for p in ctx.props))]),
        Section("crossref-groupings", "Cross-reference for groupings", groupings_body(ctx)),
        Section("crossref-characters", "Cross-reference for characters", characters_body(ctx)),
        Section("crossref-collections", "Cross-reference for collections",
                "\n".join(collection_entry(ctx, c) for c in ctx.colls)),
        Section("validation", "Validation", validation_body(ctx), [
            Section("crossref-shapes", "The shapes",
                    shapes_graph_entry(ctx) + "\n" + "\n".join(shape_entry(ctx, s) for s in ctx.shapes))]),
        Section("access", "Access and use", access_body(ctx), [Section("queries", "Queries", queries_body(ctx))]),
        Section("sources", "Sources, licence and citation", sources_body(ctx)),
        Section("references", "References", references_body(ctx), appendix=True),
        Section("changes", "Changes", changes_body(ctx), appendix=True),
    ]
    assign_numbers(sections)
    body_sections = "\n".join(render_section(ctx, s, 2) for s in sections)
    repo = f"<dt>Repository</dt><dd>{a(REPO_URL, esc(REPO_URL))}</dd>\n" if REPO_URL else ""
    issues = f' through the {a(REPO_URL + "/issues", "issue tracker")} of the repository' if REPO_URL else ""
    head = f"""<div class="head">
<p class="badge">SKOS concept scheme · specification</p>
<h1 id="{ctx.uid("title")}">{esc(title)}</h1>
<h2 id="{ctx.uid("subtitle")}">Specification of version {esc(version)}, <time datetime="{esc(modified)}">{esc(long_date(modified))}</time></h2>
<dl>
<dt>This version</dt><dd>{a(SITE_URL, esc(SITE_URL))}</dd>
<dt>Data</dt><dd>{a("mahabharata_characters.ttl", "mahabharata_characters.ttl")} (RDF 1.1 Turtle, {len(g):,} triples) · {a("shapes.ttl", "shapes.ttl")} (SHACL, {len(ctx.sg):,} triples)</dd>
<dt>Namespaces</dt><dd><code>mbh:</code> {a("characters.html", esc(str(MBH)))}<br/><code>mbhx:</code> {a("schema.html", esc(str(MBHX)))}<br/><code>mbsh:</code> {a("shapes.html", esc(str(MBSH)))}</dd>
{repo}<dt>Author</dt><dd>{esc(AUTHOR)}</dd>
<dt>Licence</dt><dd>{a("https://creativecommons.org/licenses/by-sa/4.0/", "CC BY-SA 4.0")} for the data and this document; MIT for the scripts</dd>
</dl>
<hr/>
</div>
<section id="{ctx.uid("abstract")}"><h2>Abstract</h2><p>{esc(abstract)}</p></section>
<section id="{ctx.uid("sotd")}"><h2>Status of this document</h2>
<p>This document is the specification of version {esc(version)} of the concept scheme <i>{esc(title)}</i>. It is generated from the data file <a href="mahabharata_characters.ttl">mahabharata_characters.ttl</a> by <code>scripts/render_site.py</code>, and every count, list and entry in it is computed from that file; the data is normative and this document describes it. The data was last modified on {esc(long_date(modified))}.</p>
<p>The layout follows W3C vocabulary specifications such as {cites("[PROV-O]")}. This is not a W3C publication.</p>
<p>The terms and IRIs of version 1 are stable: a change that removes or renames a term raises the major version. Changes are recorded in <a href="#changes">Changes</a> and in the repository's <code>CHANGELOG.md</code>. Corrections and additions are welcome{issues}; <code>CONTRIBUTING.md</code> in the repository has the template for a new character and the conventions.</p>
</section>
<nav id="{ctx.uid("toc")}"><h2>Table of contents</h2>{render_toc(sections)}</nav>
"""
    footer = (f'<footer><p>Generated from <a href="mahabharata_characters.ttl">mahabharata_characters.ttl</a> and '
              f'<a href="shapes.ttl">shapes.ttl</a> by <code>scripts/render_site.py</code>. Data and text: CC BY-SA 4.0. '
              f'Author: {esc(AUTHOR)}.</p></footer>')
    description = (f"Specification of the SKOS concept scheme of the characters of the Mahabharata: {len(ctx.chars)} "
                   f"characters, {len(ctx.groups)} groupings, {len(ctx.colls)} collections, with labels in English, "
                   "Devanagari and IAST and mappings to Wikidata and DBpedia.")
    return html_page(f"{title}: a SKOS concept scheme", description, head + body_sections + "\n" + footer,
                     jsonld(ctx, title, abstract, version, created, modified))


def namespace_doc(ctx: Ctx, prefix: str, ns: str, default: str, terms: list, what: str) -> str:
    items = "".join(f'<li>{term_link(ctx, t).replace("#", "./#", 1)} <code>{esc(qname(t))}</code></li>' for t in terms)
    first = terms[0]
    script = ('<script>\n(function () {\n  var h = window.location.hash;\n'
              '  var base = window.location.protocol === "file:" ? "./index.html" : "./";\n'
              f'  window.location.replace(base + (h.length > 1 ? h : "#{default}"));\n'
              '})();\n</script>\n')
    body = f"""<div class="head"><p class="badge">Namespace document</p>
<h1>Namespace <code>{esc(prefix)}:</code></h1>
<h2>{esc(ns)}</h2></div>
<p>This is the namespace document for <code>{esc(ns)}</code>, the {esc(what)} of the SKOS concept scheme <i>Characters of the Mahabharata</i>. Each term is described in the <a href="./">specification</a>; this page forwards a browser to the entry named by the fragment of the IRI, so <code>{esc(ns + anchor(first))}</code> opens the entry for {term_link(ctx, first).replace("#", "./#", 1)}. The data is served as RDF Turtle at <a href="mahabharata_characters.ttl">mahabharata_characters.ttl</a> and the shapes at <a href="shapes.ttl">shapes.ttl</a>.</p>
<h2>Terms</h2>
<ul>{items}</ul>"""
    return html_page(f"{prefix}: namespace of Characters of the Mahabharata", f"Namespace document for {ns}", body,
                     f'<meta name="robots" content="noindex,follow"/>\n{script}')


# --------------------------------------------------------------------------- checks and assembly

def verify(html: str, name: str, index_ids: set[str]) -> None:
    """Well-formed markup, and every internal link has its anchor (in this page, or in index.html for ./# links)."""
    try:
        ET.fromstring(html.encode("utf-8"))
    except ET.ParseError as e:
        raise SystemExit(f"render_site: {name} is not well-formed markup: {e}")
    own_ids = set(re.findall(r' id="([^"]+)"', html))
    dangling = set(re.findall(r'href="#([^"]+)"', html)) - own_ids
    dangling |= set(re.findall(r'href="\./#([^"]+)"', html)) - index_ids
    if dangling:
        raise SystemExit(f"render_site: {name} links to anchors that do not exist: " + ", ".join(sorted(dangling)))


def main(argv: list[str]) -> int:
    check = "--check" in argv
    g = Graph()
    g.parse(TTL, format="turtle")
    sg = Graph()
    sg.parse(SHAPES, format="turtle")
    ctx = Ctx(g, sg, term_order(TTL.read_text(encoding="utf-8") + "\n" + SHAPES.read_text(encoding="utf-8")))
    index = spec_page(ctx)
    outputs = {
        ROOT / "index.html": index,
        ROOT / "characters.html": namespace_doc(ctx, "mbh", str(MBH), "characters", ctx.groups + ctx.chars + ctx.colls,
                                                "concepts and collections"),
        ROOT / "schema.html": namespace_doc(ctx, "mbhx", str(MBHX), "schema", ctx.classes + ctx.props,
                                            "classes and properties"),
        ROOT / "shapes.html": namespace_doc(ctx, "mbsh", str(MBSH), "shapes", ctx.shapes, "SHACL shapes"),
    }
    index_ids = set(re.findall(r' id="([^"]+)"', index))
    for path, html in outputs.items():
        verify(html, path.name, index_ids)
    stale = []
    for path, content in outputs.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        stale.append(path.name)
        if not check:
            path.write_text(content, encoding="utf-8")
    if check:
        if stale:
            print("The website is out of date:", ", ".join(stale))
            print("Run: python scripts/render_site.py")
            return 1
        print("The website is up to date.")
        return 0
    print("Wrote:", ", ".join(stale) if stale else "nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
