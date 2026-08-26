.PHONY: setup run check test redis worker beat reconcile

setup:
	pip install -r requirements.txt
	python manage.py migrate
	python manage.py bootstrap_demo

run:
	daphne -b 127.0.0.1 -p 8000 config.asgi:application

redis:
	docker compose up -d redis

check:
	python manage.py makemigrations --check --dry-run
	python manage.py check
	python -m pytest -q

test:
	python -m pytest -q

worker:  ## Lancer le worker Celery (tâches d'exploitation)
	celery -A config worker -l info

beat:  ## Lancer le planificateur Celery beat (tâches périodiques)
	celery -A config beat -l info

reconcile:  ## Réconcilier les panes orphelins (hors génération courante)
	python manage.py reconcile_panes
