# Changelog

All notable changes to the concept scheme are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the version is carried in the Turtle file as `owl:versionInfo` on `mb:characters` and `mb:schema`.

## [1.0.0] - 2026-11-08

First release.

- Concept scheme `mb:characters` with 111 characters and 37 groupings under 8 top concepts (House of Kuru, Yadavas, Panchala, other royal houses, Brahmins and sages, Sutas, deities and celestial beings, Rakshasas/Nagas/Asuras).
- Extension schema `mbhx:` with the classes `Character` and `Grouping`, the datatype property `fellOnWarDay`, and twelve relation properties, each with a declared inverse or declared symmetric, all sub-properties of `skos:related`.
- Labels in English, Devanagari Sanskrit and IAST; epithets and names in disguise as alternative labels; spelling variants as hidden labels.
- 11 collections, 3 of them ordered (Pandavas by birth, sons of Draupadi, Kaurava commanders in sequence).
- Mappings to Wikidata and DBpedia (`exactMatch`, `closeMatch`) and to English Wikipedia (`foaf:isPrimaryTopicOf`).
- SHACL shapes for the SKOS integrity conditions and the conventions of the scheme; validator, documentation generator and export script; GitHub Actions workflow.
- Namespace `https://mahabharata.tanay.uk/`: concepts and collections under `characters#`, the schema under `schema#`, the shapes under `shapes#`. Every IRI resolves to its entry in the specification.
- Specification website at [mahabharata.tanay.uk](https://mahabharata.tanay.uk/) (`index.html`), generated from the data by `scripts/render_site.py`, with namespace documents that forward each IRI to its entry; GitHub Pages configuration (`CNAME`, `.nojekyll`).
