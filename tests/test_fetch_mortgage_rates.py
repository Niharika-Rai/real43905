import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from pipeline.fetch_mortgage_rates import (
    FALLBACK_RATES,
    _RATE_LABEL_ALIASES,
    fetch_live_rates,
    get_live_rates_partial,
)


def test_fallback_rates_cover_every_label():
    assert set(FALLBACK_RATES.keys()) == set(_RATE_LABEL_ALIASES.keys())
    for value in FALLBACK_RATES.values():
        assert 0.5 <= value <= 20.0


_SAMPLE_HTML = """
<html><body>
<table>
<tr><td>30 Yr. Fixed</td><td>6.58%</td></tr>
<tr><td>15 Yr. Fixed</td><td>5.80%</td></tr>
<tr><td>30 Yr. Jumbo</td><td>6.70%</td></tr>
<tr><td>7/6 SOFR ARM</td><td>5.95%</td></tr>
<tr><td>30 Yr. FHA</td><td>6.20%</td></tr>
<tr><td>30 Yr. VA</td><td>6.05%</td></tr>
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


def test_get_live_rates_partial_parses_clean_page():
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(_SAMPLE_HTML)):
        rates = get_live_rates_partial()
    assert rates == {
        "30-Year Fixed": 6.58,
        "15-Year Fixed": 5.80,
        "Jumbo 30-Year Fixed": 6.70,
        "7/6 SOFR ARM (initial rate)": 5.95,
        "FHA 30-Year Fixed": 6.20,
        "VA 30-Year Fixed": 6.05,
    }


def test_get_live_rates_partial_matches_older_arm_label_too():
    # MND used to label this product "5/1 ARM" before switching to "7/6
    # SOFR ARM" -- the alias list keeps the old phrasing as a fallback
    older_html = _SAMPLE_HTML.replace("7/6 SOFR ARM", "5/1 ARM")
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(older_html)):
        rates = get_live_rates_partial()
    assert rates["7/6 SOFR ARM (initial rate)"] == 5.95


def test_get_live_rates_partial_one_missing_label_does_not_drop_the_others():
    # this is the real-world bug this partial-matching design fixes: MND
    # renamed its ARM product and the old all-or-nothing matching silently
    # zeroed out every other rate that parsed just fine
    html_missing_arm = _SAMPLE_HTML.replace(
        "<tr><td>7/6 SOFR ARM</td><td>5.95%</td></tr>", ""
    )
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(html_missing_arm)):
        rates = get_live_rates_partial()
    assert "7/6 SOFR ARM (initial rate)" not in rates
    assert rates["30-Year Fixed"] == 6.58
    assert rates["15-Year Fixed"] == 5.80
    assert rates["Jumbo 30-Year Fixed"] == 6.70
    assert rates["FHA 30-Year Fixed"] == 6.20
    assert rates["VA 30-Year Fixed"] == 6.05


def test_get_live_rates_partial_empty_on_request_failure():
    with patch("pipeline.fetch_mortgage_rates.requests.get", side_effect=requests.ConnectionError("blocked")):
        assert get_live_rates_partial() == {}


def test_get_live_rates_partial_empty_on_http_error():
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response("", status=503)):
        assert get_live_rates_partial() == {}


def test_get_live_rates_partial_ignores_implausible_value():
    # a stray "150%" (e.g. from an unrelated "up 150%" blurb) near the label
    # should not be accepted as that loan type's rate
    bad_html = _SAMPLE_HTML.replace("6.58%", "150.00%")
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(bad_html)):
        rates = get_live_rates_partial()
    assert "30-Year Fixed" not in rates
    assert rates["15-Year Fixed"] == 5.80  # the other rows still parse fine


# ---------------------------------------- fetch_live_rates (strict wrapper) --
def test_fetch_live_rates_parses_clean_page():
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(_SAMPLE_HTML)):
        rates = fetch_live_rates()
    assert rates == {
        "30-Year Fixed": 6.58,
        "15-Year Fixed": 5.80,
        "Jumbo 30-Year Fixed": 6.70,
        "7/6 SOFR ARM (initial rate)": 5.95,
        "FHA 30-Year Fixed": 6.20,
        "VA 30-Year Fixed": 6.05,
    }


def test_fetch_live_rates_returns_none_on_request_failure():
    with patch("pipeline.fetch_mortgage_rates.requests.get", side_effect=requests.ConnectionError("blocked")):
        assert fetch_live_rates() is None


def test_fetch_live_rates_returns_none_on_incomplete_page():
    # missing the Jumbo and ARM rows -- the strict wrapper requires all six
    partial_html = """
    <html><body>
    <tr><td>30 Yr. Fixed</td><td>6.58%</td></tr>
    <tr><td>15 Yr. Fixed</td><td>5.80%</td></tr>
    </body></html>
    """
    with patch("pipeline.fetch_mortgage_rates.requests.get", return_value=_mock_response(partial_html)):
        assert fetch_live_rates() is None
