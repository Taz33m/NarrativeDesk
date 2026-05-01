.PHONY: test smoke report web-data

PYTHON ?= python3
PYTHON_ENV = PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src
EVENT_FIXTURE = data/fixtures/synthetic_event.json
VALIDATION_FIXTURE = data/fixtures/synthetic_validation.json

web-data:
	$(PYTHON_ENV) $(PYTHON) scripts/generate_demo_assets.py

test:
	$(PYTHON_ENV) $(PYTHON) -m unittest discover -s tests

smoke report: web-data
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli $(EVENT_FIXTURE) --validation $(VALIDATION_FIXTURE) --out examples/sample_report.md --ledger-out artifacts/sample_ledger.json
