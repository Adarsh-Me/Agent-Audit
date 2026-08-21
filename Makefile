.PHONY: dev test lint validate seed-demo serve-demo e2e demo-check db-up db-down

dev:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

test:
	cd backend && python -m pytest -q

lint:
	ruff check backend

validate:
	cd backend && python -m pytest tests/validation -q

seed-demo:
	python demo-store/generate.py
	cd backend && python -m scripts.seed_demo

serve-demo:
	cd demo-store/site && python -m http.server 8080

e2e:
	cd frontend && npx playwright test

demo-check:
	cd backend && python -m scripts.demo_check

db-up:
	docker compose up -d db

db-down:
	docker compose down
