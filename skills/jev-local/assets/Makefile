# Local jev (open-jev) wrapper. Apple silicon only (MLX). Add open-jev/ to .gitignore.
OPENJEV ?= open-jev
MODEL   ?= models/gemma-3-4b-it-4bit
HF_REPO ?= mlx-community/gemma-3-4b-it-4bit
PORT    ?= 8000

.PHONY: help setup serve health

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup: ## clone open-jev, create venv, download $(HF_REPO)
	@test -d $(OPENJEV) || git clone --depth 1 https://github.com/daseinlabs/open-jev $(OPENJEV)
	$(MAKE) -C $(OPENJEV) setup MODEL=$(MODEL) HF_REPO=$(HF_REPO)

serve: ## start jev server on :$(PORT)  (POST /v1/systemone, GET /health)
	$(MAKE) -C $(OPENJEV) serve MODEL=$(MODEL) PORT=$(PORT)

health: ## check the server
	@curl -s localhost:$(PORT)/health; echo
