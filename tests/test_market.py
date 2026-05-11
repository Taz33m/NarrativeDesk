import unittest

from narrativedesk.market import MarketBar, compute_event_market_metrics


def _snapshot_with_bar_times(**overrides):
    snapshot = {
        "event_bar": {
            "symbol": "TEST",
            "open": 100,
            "close": 88.6,
            "volume": 240,
            "average_volume": 100,
            "timestamp": "2025-08-07T09:59:00-04:00",
        },
        "sector_bar": {
            "symbol": "SECTOR",
            "open": 100,
            "close": 99.2,
            "as_of": "2025-08-07T10:00:00-04:00",
        },
        "peer_bars": [
            {
                "symbol": "PEER-A",
                "open": 100,
                "close": 98.1,
                "timestamp": "2025-08-07T09:58:00-04:00",
            },
            {
                "symbol": "PEER-B",
                "open": 100,
                "close": 98.8,
                "as_of": "2025-08-07T09:57:00-04:00",
            },
            {
                "symbol": "PEER-C",
                "open": 100,
                "close": 99.4,
                "timestamp": "2025-08-07T09:56:00-04:00",
            },
        ],
    }
    for key, value in overrides.items():
        snapshot[key] = value
    return snapshot


class MarketMetricTests(unittest.TestCase):
    def test_market_bar_return_and_volume_ratio(self):
        bar = MarketBar(symbol="TEST", open=100, close=88.6, volume=240, average_volume=100)

        self.assertEqual(bar.simple_return(), -0.114)
        self.assertEqual(bar.volume_ratio(), 2.4)

    def test_event_market_metrics_use_peer_median(self):
        metrics = compute_event_market_metrics(
            {
                "event_bar": {
                    "symbol": "TEST",
                    "open": 100,
                    "close": 88.6,
                    "volume": 240,
                    "average_volume": 100,
                },
                "sector_bar": {"symbol": "SECTOR", "open": 100, "close": 99.2},
                "peer_bars": [
                    {"symbol": "PEER-A", "open": 100, "close": 98.1},
                    {"symbol": "PEER-B", "open": 100, "close": 98.8},
                    {"symbol": "PEER-C", "open": 100, "close": 99.4},
                ],
            }
        )

        self.assertEqual(metrics["daily_return"], -0.114)
        self.assertEqual(metrics["peer_median_return"], -0.012)
        self.assertEqual(metrics["abnormal_return"], -0.102)
        self.assertEqual(metrics["sector_etf_return"], -0.008)
        self.assertEqual(metrics["volume_ratio"], 2.4)

    def test_event_market_metrics_allows_bar_timestamps_at_or_before_replay_lock(self):
        metrics = compute_event_market_metrics(
            _snapshot_with_bar_times(),
            replay_timestamp="2025-08-07T10:00:00-04:00",
        )

        self.assertEqual(metrics["daily_return"], -0.114)
        self.assertEqual(metrics["peer_median_return"], -0.012)

    def test_event_market_metrics_rejects_future_event_bar_timestamp(self):
        snapshot = _snapshot_with_bar_times(
            event_bar={
                "symbol": "TEST",
                "open": 100,
                "close": 88.6,
                "timestamp": "2025-08-07T10:01:00-04:00",
            }
        )

        with self.assertRaisesRegex(ValueError, "TEST market bar timestamp .* after replay timestamp"):
            compute_event_market_metrics(
                snapshot,
                replay_timestamp="2025-08-07T10:00:00-04:00",
            )

    def test_event_market_metrics_rejects_missing_bar_replay_timestamp(self):
        snapshot = _snapshot_with_bar_times(
            event_bar={
                "symbol": "TEST",
                "open": 100,
                "close": 88.6,
            }
        )

        with self.assertRaisesRegex(ValueError, "TEST market bar must include timestamp or as_of"):
            compute_event_market_metrics(
                snapshot,
                replay_timestamp="2025-08-07T10:00:00-04:00",
            )

    def test_event_market_metrics_rejects_future_peer_bar_as_of(self):
        snapshot = _snapshot_with_bar_times(
            peer_bars=[
                {
                    "symbol": "PEER-A",
                    "open": 100,
                    "close": 98.1,
                    "timestamp": "2025-08-07T09:58:00-04:00",
                },
                {
                    "symbol": "PEER-B",
                    "open": 100,
                    "close": 98.8,
                    "as_of": "2025-08-07T10:01:00-04:00",
                },
            ],
        )

        with self.assertRaisesRegex(ValueError, "PEER-B market bar timestamp .* after replay timestamp"):
            compute_event_market_metrics(
                snapshot,
                replay_timestamp="2025-08-07T10:00:00-04:00",
            )

    def test_event_market_metrics_rejects_naive_bar_timestamp(self):
        snapshot = _snapshot_with_bar_times(
            event_bar={
                "symbol": "TEST",
                "open": 100,
                "close": 88.6,
                "timestamp": "2025-08-07T10:00:00",
            }
        )

        with self.assertRaisesRegex(ValueError, "TEST market bar timestamp must include a timezone offset"):
            compute_event_market_metrics(
                snapshot,
                replay_timestamp="2025-08-07T10:00:00-04:00",
            )

    def test_zero_open_price_fails(self):
        bar = MarketBar(symbol="BAD", open=0, close=1)

        with self.assertRaises(ValueError):
            bar.simple_return()


if __name__ == "__main__":
    unittest.main()
