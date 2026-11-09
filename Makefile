PYTHON ?= python3

.PHONY: help install validate docs site check export clean

help:            ## Show the available targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install:         ## Install rdflib and pyshacl
	$(PYTHON) -m pip install -r requirements.txt

validate:        ## Parse the Turtle, run the SHACL shapes, check for dangling IRIs
	$(PYTHON) scripts/validate.py

docs:            ## Regenerate docs/, the generated blocks in README.md and the website from the data
	$(PYTHON) scripts/render_docs.py
	$(PYTHON) scripts/render_site.py

site:            ## Regenerate only the website (index.html and the namespace documents)
	$(PYTHON) scripts/render_site.py

check: validate  ## What CI runs: validate, then fail if the generated docs or the website are stale
	$(PYTHON) scripts/render_docs.py --check
	$(PYTHON) scripts/render_site.py --check

export:          ## Write RDF/XML, JSON-LD and N-Triples copies to dist/
	$(PYTHON) scripts/export.py

clean:           ## Remove dist/ and Python caches
	rm -rf dist scripts/__pycache__
