import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from pipeline.fetch_mortgage_rates import FALLBACK_RATES, _RATE_LABEL_ALIASES, fetch_live_rates


def test_fallback_rates_cover_every_label():
    assert set(FALLBACK_RATES.keys()) == set(_RATE_LABEL_ALIASES.keys())
    for value in FALLBACK_RATES.values():
        assert 0.5 <= value <= 20.0


_SAMPLE_HTML = """
<html><body>
<table>
<tr><td>30 Yr. Fixed</td><td>6.58%</td></tr>
<tr><td>15 Yr. Fixed</td><td>5.80%</td></tr>
<tr><td>30 Yr. FHA</td><td>6.20%</td></tr>
<tr><td>30 Yr. VA</td><td>6.05%</td></tr>
<tr><td>30 Yr. Jumbo</td><td>6.70%</td></tr>
<tr><td>5/1 ARM</td><td>5.95%</td></tr>
</table>
</body></html>
"""


def _mock_response(text, status=200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status} error")
    return resp


def test_fetch_live_rates_parses_clean_page():
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(_SAMPLE_HTML)):
        rates = fetch_live_rates()
    assert rates == {
        "30-Year Fixed": 6.58,
        "15-Year Fixed": 5.80,
        "FHA 30-Year Fixed": 6.20,
        "VA 30-Year Fixed": 6.05,
        "Jumbo 30-Year Fixed": 6.70,
        "5/1 ARM (initial rate)": 5.95,
    }


def test_fetch_live_rates_returns_none_on_request_failure():
    with patch("pipeline.fetch_mortgage_rates.requests.get", side_effect=requests.ConnectionError("blocked")):
        assert fetch_live_rates() is None


def test_fetch_live_rates_returns_none_on_http_error():
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response("", status=503)):
        assert fetch_live_rates() is None


def test_fetch_live_rates_returns_none_on_incomplete_page():
    # missing the Jumbo and ARM rows -- a partial match should never be returned
    partial_html = """
    <html><body>
    <tr><td>30 Yr. Fixed</td><td>6.58%</td></tr>
    <tr><td>15 Yr. Fixed</td><td>5.80%</td></tr>
    </body></html>
    """
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(partial_html)):
        assert fetch_live_rates() is None


def test_fetch_live_rates_ignores_implausible_value():
    # a stray "150%" (e.g. from an unrelated "up 150%" blurb) near the label
    # should not be accepted as the rate
    bad_html = _SAMPLE_HTML.replace("6.58%", "150.00%")
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(bad_html)):
        assert fetch_live_rates() is None
