# Contributing

Corrections, additions and better Sanskrit are all welcome. This page explains how the file is organised, what a new character needs, and what to run before opening a pull request.

## Before you start

```sh
pip install -r requirements.txt   # rdflib and pyshacl
make validate                     # must pass on a clean checkout
```

`mahabharata_characters.ttl` is the only source of truth. `README.md` (the marked blocks) and everything under `docs/` are generated from it by `scripts/render_docs.py`; the website (`index.html`, `characters.html`, `schema.html`, `shapes.html`) by `scripts/render_site.py`. Do not edit any of them by hand.

## Where things go in the Turtle file

| Section | Holds |
|---|---|
| 1 Concept scheme | Metadata of the scheme, the modelling conventions as a `skos:scopeNote`, the top concepts. |
| 2 Extension schema | `mbhx:Character`, `mbhx:Grouping`, `mbhx:fellOnWarDay` and the relation properties. Change only when a new kind of relation is needed. |
| 3 Groupings | The hierarchy: lineages, generations, royal houses, orders, classes of being. |
| 4 Characters | One block per character, grouped by the grouping it belongs to, in narrative order. |
| 5 Collections | Cross-cutting sets: war sides, survivors, birth order, narrative frame. |

## Adding a character

Copy this template into the right part of section 4 and fill every line. Delete a line only if the character has nothing for it (no epithets, no spelling variants, no Wikidata item).

```turtle
mbh:LOCAL-NAME a mbhx:Character, skos:Concept ;
    skos:inScheme mb:characters ;
    skos:broader mbh:GROUPING ;                       # one or more groupings, never a character
    skos:prefLabel "Name"@en, "देवनागरी"@sa-Deva, "IAST stem"@sa-Latn ;
    skos:altLabel "Epithet"@en, "Patronymic"@en ;      # epithets, patronymics, names in disguise
    skos:hiddenLabel "Common spelling"@en ;            # English spelling variants only
    skos:definition "One sentence: who this is and what they do in the story."@en ;
    skos:note "Further narrative detail if the definition cannot hold it."@en ;
    mbhx:childOf mbh:PARENT, mbh:PARENT ;              # relations, in the direction the property names
    mbhx:killedBy mbh:KILLER ;
    mbhx:fellOnWarDay 14 ;                             # only for deaths in the Kurukshetra war
    skos:exactMatch wd:QNNNN, dbr:Article_Title ;      # or skos:closeMatch when the item is wider
    foaf:isPrimaryTopicOf wp:Article_Title .           # or rdfs:seeAlso the list article when there is no article
```

Conventions the SHACL shapes enforce:

- **Local name**: lower-case ASCII, hyphens between words, disambiguated with a suffix when needed (`chitrangada-kuru`, `chitrangada-manipura`). Never reuse a local name.
- **Preferred label**: exactly one per language, English required. English preferred labels are unique across the scheme; disambiguate in the label itself, as in *Uttara (prince of Matsya)*. Sanskrit uses the dictionary stem (*Aśvatthāman*); put the nominative (*Aśvatthāmā*) in `skos:altLabel` if it is the familiar form.
- **Alternative labels** are names the character is actually called by in the epic or in the tradition. **Hidden labels** are spellings, English only.
- **Definition**: present tense, one sentence, states who the character is and what part they play. Paraphrase; do not copy Wikipedia text.
- **Relations**: stated once, in the direction named by the property (`childOf` on the child, `killedBy` on the one killed, `studentOf` on the student). Never write `parentOf`, `killed`, `teacherOf` or another inverse; the schema declares them and inference supplies them. Symmetric relations (`spouseOf`, `siblingOf`, `friendOf`, `rivalOf`) once per pair. Use `siblingOf` only when the shared parent is not a concept.
- **Mappings**: `skos:exactMatch` to Wikidata and DBpedia when the resource is this character; `skos:closeMatch` when it is wider. Resolve the Wikidata item through the Wikipedia API: `https://en.wikipedia.org/w/api.php?action=query&prop=pageprops&ppprop=wikibase_item&redirects=1&format=json&titles=Article_Title`. A character with no article of its own gets `rdfs:seeAlso <https://en.wikipedia.org/wiki/List_of_characters_in_the_Mahabharata>`.
- **Groupings**: add one only when at least one character belongs to it. A new royal house goes under `mbh:other-royal-houses` with a `closeMatch` to the kingdom's Wikidata item.

If the character belongs to a side in the war, add it to `mbh:coll-pandava-side` or `mbh:coll-kaurava-side`, and to `mbh:coll-survivors` if it survived.

## Correcting a fact

Narrative facts follow the Wikipedia articles, which follow the Critical Edition. If a reading differs between recensions, keep the commonly cited reading in the structured statement and record the variant in a `skos:note`. Please cite the article or passage in the pull request.

## Before opening a pull request

```sh
make validate   # syntax, SHACL shapes, dangling IRIs
make docs       # regenerate README blocks, docs/ and the website
```

Commit the regenerated documentation and website together with the data change. CI runs `make check`, which is the validator plus `render_docs.py --check` and `render_site.py --check`, and fails if any of them does not pass. The site generator also fails on a duplicate anchor, a dangling internal link, ill-formed markup, or a statement in the data that no entry shows, so a new property needs a row in the matching entry function of `scripts/render_site.py`.

## Scope

In scope: characters of the Mahabharata proper, including its frame story and the deities who act in it. Out of scope: characters who appear only in the Ramopakhyana retelling of the Ramayana, and figures from regional retellings, unless clearly marked as such in a `skos:scopeNote`.
