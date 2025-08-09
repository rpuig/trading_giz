SHELL := /bin/bash

.PHONY: help dev scan-once ui build up down

help:
	@echo "Targets:"
	@echo "  dev        - run scanner loop + UI locally (two shells)"
	@echo "  scan-once  - run a single scanner pass"
	@echo "  ui         - run Next.js UI"
	@echo "  build      - docker-compose build"
	@echo "  up         - docker-compose up -d"
	@echo "  down       - docker-compose down"

scan-once:
	cd scanner && python scanner.py --print

ui:
	cd ui && npm install && npm run dev

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down
