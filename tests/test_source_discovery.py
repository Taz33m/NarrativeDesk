import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from narrativedesk import cli
from narrativedesk.real_provenance import draft_real_case
from narrativedesk.source_discovery import (
    DiscoveryCandidate,
    discovery_candidates_from_sonar_response,
    discover_sources_with_sonar,
    freeze_discovery_candidates,
)


class FakePoster:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, *, payload, headers=None):
        self.calls.append({"url": url, "payload": payload, "headers": headers or {}})
        return self.response


class FakeTextFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        raise AssertionError("freeze should not request JSON")

    def get_text(self, url, *, params=None, headers=None):
        self.calls.append({"url": url, "headers": headers or {}})
        if url not in self.pages:
            raise OSError("missing page")
        return self.pages[url]


class SourceDiscoveryTests(unittest.TestCase):
    def test_sonar_search_results_become_discovery_candidates_without_message_claims(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "Generated answer should stay audit-only and never become evidence."
                    }
                }
            ],
            "search_results": [
                {
                    "title": "Apple reports second quarter results",
                    "url": "https://www.apple.com/newsroom/example",
                    "date": "2024-05-02",
                    "snippet": "Apple announced quarterly results.",
                },
                {
                    "title": "Missing date",
                    "url": "https://example.com/no-date",
                    "snippet": "No timestamp.",
                },
            ],
            "citations": ["https://example.com/citation-only"],
        }

        candidates, rejected = discovery_candidates_from_sonar_response(
            response,
            model="sonar",
            query="Apple Q2 2024",
            discovered_at="2024-05-03T15:00:00Z",
            raw_response_path="raw_response.json",
            raw_response_hash="sha256:" + "0" * 64,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].publisher_hint, "www.apple.com")
        self.assertNotIn("Generated answer", json.dumps([candidate.to_dict() for candidate in candidates]))
        self.assertEqual(len(rejected), 2)
        self.assertTrue(any("published_at_hint" in str(candidate.rejection_reason) for candidate in rejected))
        self.assertTrue(any("title" in str(candidate.rejection_reason) for candidate in rejected))

    def test_discover_sources_writes_scratch_artifacts_and_redacts_secret(self):
        response = {
            "choices": [{"message": {"content": "Audit-only answer."}}],
            "search_results": [
                {
                    "title": "Apple reports second quarter results",
                    "url": "https://www.apple.com/newsroom/example",
                    "date": "2024-05-02",
                    "snippet": "Apple announced quarterly results.",
                }
            ],
        }
        poster = FakePoster(response)
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = discover_sources_with_sonar(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                query="Apple Q2 2024 earnings",
                out_dir=tmpdir,
                api_key="pplx-secret-token-value",
                model="sonar",
                poster=poster,
                discovered_at="2024-05-03T15:00:00Z",
            )
            request_text = (Path(tmpdir) / "discovery_request.json").read_text()
            candidates = json.loads((Path(tmpdir) / "discovery_candidates.json").read_text())

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(poster.calls[0]["url"], "https://api.perplexity.ai/v1/sonar")
        self.assertEqual(poster.calls[0]["headers"]["Authorization"], "Bearer pplx-secret-token-value")
        self.assertIn("Bearer [REDACTED]", request_text)
        self.assertNotIn("pplx-secret-token-value", request_text)
        self.assertEqual(candidates["candidates"][0]["status"], "candidate")

    def test_discovery_rejects_local_or_credentialed_urls(self):
        response = {
            "search_results": [
                {
                    "title": "Local URL",
                    "url": "http://127.0.0.1:8000/internal",
                    "date": "2024-05-02",
                    "snippet": "Should not be refetched.",
                },
                {
                    "title": "Credential URL",
                    "url": "https://user:pass@example.com/article",
                    "date": "2024-05-02",
                    "snippet": "Should not include URL credentials.",
                },
            ]
        }

        candidates, rejected = discovery_candidates_from_sonar_response(
            response,
            model="sonar",
            query="Apple Q2 2024",
            discovered_at="2024-05-03T15:00:00Z",
            raw_response_path="raw_response.json",
            raw_response_hash="sha256:" + "0" * 64,
        )

        self.assertEqual(candidates, [])
        self.assertEqual(len(rejected), 2)
        self.assertTrue(all("safe_http_url" in str(item.rejection_reason) for item in rejected))

    def test_freeze_refetches_pages_and_applies_replay_lock(self):
        eligible_url = "https://finance.example.com/apple-q2"
        future_url = "https://finance.example.com/apple-q3"
        rejected_url = "https://finance.example.com/missing-meta"
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_dir = Path(tmpdir)
            _write_discovery_candidates(discovery_dir, [eligible_url, future_url, rejected_url])
            pages = {
                eligible_url: _html_page(
                    title="Apple Q2 earnings",
                    site="Finance Example",
                    published_at="2024-05-02T22:30:00Z",
                    body="Apple reported quarterly results with services strength and iPhone pressure." * 4,
                ),
                future_url: _html_page(
                    title="Apple later validation",
                    site="Finance Example",
                    published_at="2024-05-20T12:00:00Z",
                    body="Later commentary discussed estimate revisions and validation evidence." * 4,
                ),
                rejected_url: "<html><title>No metadata</title><body>Too little metadata for evidence.</body></html>",
            }
            summary = freeze_discovery_candidates(
                discovery_dir=discovery_dir,
                replay_lock="2024-05-03T10:00:00-04:00",
                fetcher=FakeTextFetcher(pages),
                generated_at="2024-05-21T15:00:00Z",
            )
            frozen = json.loads((discovery_dir / "frozen" / "source_candidates.json").read_text())
            rejected = json.loads((discovery_dir / "frozen" / "rejected_candidates.json").read_text())

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["eligible_candidates"], 1)
        self.assertEqual(summary["blocked_future_candidates"], 1)
        self.assertEqual(summary["rejected_candidates"], 1)
        self.assertEqual(
            sorted(candidate["replay_status"] for candidate in frozen["candidates"]),
            ["blocked_future", "eligible"],
        )
        self.assertIn("missing_or_invalid", rejected["rejected_candidates"][0]["rejection_reason"])
        self.assertNotIn("Apple announced quarterly results", json.dumps(frozen))

    def test_freeze_can_append_to_normalized_dir_consumed_by_real_case_draft(self):
        eligible_url = "https://finance.example.com/apple-q2"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discovery_dir = root / "discovery"
            normalized_dir = root / "normalized"
            draft_dir = root / "draft"
            discovery_dir.mkdir()
            normalized_dir.mkdir()
            (normalized_dir / "market_bars.csv").write_text(
                "date,ticker,open,close,volume\n2024-05-02,AAPL,170,173,100\n"
            )
            _write_discovery_candidates(discovery_dir, [eligible_url])
            pages = {
                eligible_url: _html_page(
                    title="Apple Q2 earnings",
                    site="Finance Example",
                    published_at="2024-05-02T22:30:00Z",
                    body="Apple reported quarterly results with services strength and iPhone pressure." * 4,
                )
            }

            freeze_discovery_candidates(
                discovery_dir=discovery_dir,
                replay_lock="2024-05-03T10:00:00-04:00",
                normalized_dir=normalized_dir,
                fetcher=FakeTextFetcher(pages),
                generated_at="2024-05-03T15:00:00Z",
            )
            draft = draft_real_case(
                ticker="AAPL",
                company_name="Apple Inc.",
                event_type="earnings",
                event_date="2024-05-02",
                replay_lock="2024-05-03T10:00:00-04:00",
                normalized_dir=normalized_dir,
                out_dir=draft_dir,
            )
            config = json.loads((draft_dir / "real_case_config.json").read_text())

        self.assertEqual(draft["case_readiness"], "curator_ready")
        self.assertTrue(any(source["source_id"].startswith("PERPLEXITY-") for source in config["manual_sources"]))

    def test_cli_discover_and_freeze_can_run_with_mocked_clients(self):
        response = {
            "search_results": [
                {
                    "title": "Apple reports second quarter results",
                    "url": "https://finance.example.com/apple-q2",
                    "date": "2024-05-02",
                    "snippet": "Apple announced quarterly results.",
                }
            ]
        }
        page_fetcher = FakeTextFetcher(
            {
                "https://finance.example.com/apple-q2": _html_page(
                    title="Apple Q2 earnings",
                    site="Finance Example",
                    published_at="2024-05-02T22:30:00Z",
                    body="Apple reported quarterly results with services strength and iPhone pressure." * 4,
                )
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            discovery_dir = Path(tmpdir) / "discovery"
            with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "pplx-secret-token-value"}, clear=False):
                with patch("narrativedesk.source_discovery.UrllibJsonPoster", return_value=FakePoster(response)):
                    discover_code, discover_output = _run_cli(
                        [
                            "narrativedesk.cli",
                            "real-source-discover",
                            "--ticker",
                            "AAPL",
                            "--company-name",
                            "Apple Inc.",
                            "--event-date",
                            "2024-05-02",
                            "--replay-lock",
                            "2024-05-03T10:00:00-04:00",
                            "--query",
                            "Apple Q2 2024 earnings",
                            "--out-dir",
                            str(discovery_dir),
                        ]
                    )
            with patch("narrativedesk.source_discovery.UrllibJsonFetcher", return_value=page_fetcher):
                freeze_code, freeze_output = _run_cli(
                    [
                        "narrativedesk.cli",
                        "real-source-freeze",
                        "--discovery-dir",
                        str(discovery_dir),
                        "--replay-lock",
                        "2024-05-03T10:00:00-04:00",
                    ]
                )

        self.assertEqual(discover_code, 0, discover_output)
        self.assertEqual(freeze_code, 0, freeze_output)
        self.assertEqual(json.loads(discover_output)["candidate_count"], 1)
        self.assertEqual(json.loads(freeze_output)["eligible_candidates"], 1)


def _write_discovery_candidates(discovery_dir: Path, urls: list[str]) -> None:
    discovery_dir.mkdir(parents=True, exist_ok=True)
    candidates = [
        DiscoveryCandidate(
            candidate_id=f"PERPLEXITY-DISC-{idx:03d}",
            provider="perplexity",
            model="sonar",
            query="Apple Q2",
            title=f"Candidate {idx}",
            url=url,
            published_at_hint="2024-05-02",
            publisher_hint="finance.example.com",
            snippet="Discovery snippet only.",
            discovered_at="2024-05-03T15:00:00Z",
            raw_response_path="raw_response.json",
            raw_response_hash="sha256:" + "0" * 64,
            status="candidate",
            rejection_reason=None,
        ).to_dict()
        for idx, url in enumerate(urls, start=1)
    ]
    (discovery_dir / "discovery_candidates.json").write_text(
        json.dumps({"candidates": candidates}, indent=2, sort_keys=True)
    )


def _html_page(*, title: str, site: str, published_at: str, body: str) -> str:
    return f"""
    <html>
      <head>
        <meta property="og:title" content="{title}">
        <meta property="og:site_name" content="{site}">
        <meta property="article:published_time" content="{published_at}">
      </head>
      <body><article>{body}</article></body>
    </html>
    """


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stdout = io.StringIO()
    with patch.object(sys, "argv", argv):
        with contextlib.redirect_stdout(stdout):
            code = cli.main()
    return code, stdout.getvalue()


if __name__ == "__main__":
    unittest.main()
