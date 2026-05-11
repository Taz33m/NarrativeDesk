import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from narrativedesk.case_index import register_case_index_entry, validate_case_index
from narrativedesk.source_pack import (
    build_fixture_from_source_pack,
    build_validation_fixture_template_from_source_pack,
    load_source_pack,
)

ROOT = Path(__file__).resolve().parents[1]


class CaseIndexRegistrationTests(unittest.TestCase):
    def _write_example_fixtures(self, tmpdir):
        payload = load_source_pack(ROOT / 'examples' / 'source_pack_template.json')
        event_fixture = build_fixture_from_source_pack(payload)
        validation_fixture = build_validation_fixture_template_from_source_pack(payload)
        event_path = Path(tmpdir) / 'event_fixture.json'
        validation_path = Path(tmpdir) / 'validation_fixture.json'
        event_path.write_text(json.dumps(event_fixture))
        validation_path.write_text(json.dumps(validation_fixture))
        return event_path, validation_path

    def test_register_case_index_entry_creates_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            case_index_path = Path(tmpdir) / 'case_index.json'

            result = register_case_index_entry(
                case_index_path,
                event_path,
                validation_path,
                label='EXMPL curated example',
            )
            case_index = json.loads(case_index_path.read_text())

        self.assertEqual(result['case_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(result['case_count'], 1)
        self.assertEqual(case_index['default_case_id'], 'EVT-EXAMPLE-2025-01-02')
        self.assertEqual(case_index['cases'][0]['label'], 'EXMPL curated example')

    def test_register_case_index_entry_rejects_duplicate_case_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            case_index_path = Path(tmpdir) / 'case_index.json'
            register_case_index_entry(case_index_path, event_path, validation_path)

            with self.assertRaisesRegex(ValueError, 'already exists'):
                register_case_index_entry(case_index_path, event_path, validation_path)

    def test_register_case_index_entry_rejects_mismatched_validation_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            validation = json.loads(validation_path.read_text())
            validation['event_id'] = 'EVT-MISMATCH'
            validation_path.write_text(json.dumps(validation))

            with self.assertRaisesRegex(ValueError, 'does not match event_id'):
                register_case_index_entry(Path(tmpdir) / 'case_index.json', event_path, validation_path)

    def test_cli_case_index_register_writes_output_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            seed_index_path = Path(tmpdir) / 'missing_seed.json'
            output_index_path = Path(tmpdir) / 'case_index.json'
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'case-index-register',
                    str(seed_index_path),
                    '--event-fixture',
                    str(event_path),
                    '--validation-fixture',
                    str(validation_path),
                    '--label',
                    'EXMPL curated example',
                    '--out',
                    str(output_index_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)
            case_index = json.loads(output_index_path.read_text())

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(response['ok'])
        self.assertEqual(response['case_count'], 1)
        self.assertEqual(case_index['cases'][0]['case_id'], 'EVT-EXAMPLE-2025-01-02')

    def test_validate_case_index_accepts_registered_index(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            case_index_path = Path(tmpdir) / 'case_index.json'
            register_case_index_entry(case_index_path, event_path, validation_path)

            result = validate_case_index(case_index_path)

        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual(result['case_count'], 1)
        self.assertEqual(result['valid_case_count'], 1)
        self.assertEqual(result['pending_case_count'], 1)
        self.assertEqual(result['blocked_future_source_count'], 1)
        self.assertEqual(result['validation_future_source_count'], 1)
        self.assertEqual(result['cases'][0]['validation_future_source_count'], 1)

    def test_validate_case_index_rejects_unknown_validation_future_source_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            validation = json.loads(validation_path.read_text())
            validation['future_source_ids'] = ['SRC-NOT-BLOCKED']
            validation['rows'][0]['future_source_ids'] = ['SRC-NOT-BLOCKED']
            validation_path.write_text(json.dumps(validation))
            case_index_path = Path(tmpdir) / 'case_index.json'
            register_case_index_entry(case_index_path, event_path, validation_path)

            result = validate_case_index(case_index_path)

        self.assertFalse(result['ok'])
        self.assertTrue(
            any('future_source_ids were not blocked by replay: SRC-NOT-BLOCKED' in err for err in result['errors'])
        )

    def test_validate_case_index_rejects_validation_future_source_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            validation = json.loads(validation_path.read_text())
            validation['future_source_count'] = 99
            validation_path.write_text(json.dumps(validation))
            case_index_path = Path(tmpdir) / 'case_index.json'
            case_index_path.write_text(json.dumps({
                'default_case_id': 'EVT-EXAMPLE-2025-01-02',
                'cases': [
                    {
                        'case_id': 'EVT-EXAMPLE-2025-01-02',
                        'label': 'bad validation count',
                        'event_fixture': str(event_path),
                        'validation_fixture': str(validation_path),
                    },
                ],
            }))

            result = validate_case_index(case_index_path)

        self.assertFalse(result['ok'])
        self.assertTrue(
            any('future_source_count 99 does not match 1 future_source_ids' in err for err in result['errors'])
        )

    def test_validate_case_index_rejects_duplicate_ids_and_bad_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            case_index_path = Path(tmpdir) / 'case_index.json'
            case_index_path.write_text(json.dumps({
                'default_case_id': 'MISSING',
                'cases': [
                    {
                        'case_id': 'EVT-EXAMPLE-2025-01-02',
                        'label': 'first',
                        'event_fixture': str(event_path),
                        'validation_fixture': str(validation_path),
                    },
                    {
                        'case_id': 'EVT-EXAMPLE-2025-01-02',
                        'label': 'duplicate',
                        'event_fixture': str(event_path),
                        'validation_fixture': str(validation_path),
                    },
                ],
            }))

            result = validate_case_index(case_index_path)

        self.assertFalse(result['ok'])
        self.assertTrue(any('default_case_id MISSING' in err for err in result['errors']))
        self.assertTrue(any('duplicates EVT-EXAMPLE-2025-01-02' in err for err in result['errors']))

    def test_validate_case_index_rejects_non_list_cases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_index_path = Path(tmpdir) / 'case_index.json'
            case_index_path.write_text(json.dumps({
                'default_case_id': 'EVT-EXAMPLE-2025-01-02',
                'cases': {'case_id': 'EVT-EXAMPLE-2025-01-02'},
            }))

            result = validate_case_index(case_index_path)

        self.assertFalse(result['ok'])
        self.assertTrue(any('at least one case' in err for err in result['errors']))

    def test_validate_case_index_rejects_inline_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            event_path, validation_path = self._write_example_fixtures(tmpdir)
            event_fixture = json.loads(event_path.read_text())
            event_fixture['validation'] = {'rows': []}
            event_path.write_text(json.dumps(event_fixture))
            case_index_path = Path(tmpdir) / 'case_index.json'
            register_case_index_entry(case_index_path, event_path, validation_path)

            result = validate_case_index(case_index_path)

        self.assertFalse(result['ok'])
        self.assertTrue(any('must not contain inline validation data' in err for err in result['errors']))

    def test_cli_case_index_validate_reports_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            case_index_path = Path(tmpdir) / 'case_index.json'
            case_index_path.write_text(json.dumps({
                'default_case_id': 'MISSING',
                'cases': [],
            }))
            result = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'narrativedesk.cli',
                    'case-index-validate',
                    str(case_index_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 1)
        self.assertFalse(response['ok'])
        self.assertTrue(any('at least one case' in err for err in response['errors']))


if __name__ == '__main__':
    unittest.main()
