.PHONY: test smoke report web-data evaluate source-pack-smoke real-pack-smoke

PYTHON ?= python3
PYTHON_ENV = PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src
EVENT_FIXTURE = data/fixtures/synthetic_event.json
VALIDATION_FIXTURE = data/fixtures/synthetic_validation.json

web-data:
	$(PYTHON_ENV) $(PYTHON) scripts/generate_demo_assets.py

test:
	$(PYTHON_ENV) $(PYTHON) -m unittest discover -s tests

smoke report: web-data
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli replay $(EVENT_FIXTURE) --out examples/sample_report.md --ledger-out artifacts/sample_ledger.json

evaluate:
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli case-index-validate data/fixtures/case_index.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli evaluate-cases

source-pack-smoke:
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli source-pack-preview examples/source_pack_template.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli source-pack-readiness examples/source_pack_template.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli source-pack-bundle examples/source_pack_template.json --out-dir .codex-work/example_bundle --label "EXMPL source-pack example"
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli source-pack-ingest examples/source_pack_template.json --out .codex-work/example_event_fixture.json --validation-out .codex-work/example_validation_fixture.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli validation-validate .codex-work/example_validation_fixture.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli case-index-register .codex-work/example_case_index_seed.json --event-fixture .codex-work/example_event_fixture.json --validation-fixture .codex-work/example_validation_fixture.json --label "EXMPL source-pack example" --out .codex-work/example_case_index.json
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli case-index-validate .codex-work/example_case_index.json

real-pack-smoke:
	$(PYTHON_ENV) $(PYTHON) -m narrativedesk.cli real-pack-check examples/real_case_config_template.json
	$(PYTHON_ENV) $(PYTHON) scripts/run_real_pack_smoke.py
