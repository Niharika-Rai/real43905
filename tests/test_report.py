import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

from metros import metros_frame
from report import build_pdf_report
from scoring import score_metros


@pytest.fixture
def scored():
    df = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "metro_dataset.csv"))
    ref = metros_frame()[["cbsa", "lat", "lon", "state", "population"]]
    df["cbsa"] = df["cbsa"].astype(str).str.zfill(5)
    ref["cbsa"] = ref["cbsa"].astype(str).str.zfill(5)
    df = df.merge(ref, on="cbsa", how="left")
    return score_metros(df)


_MODEL_CONTROLS = {
    "alpha": 0.5,
    "ami_tier_pct": 60,
    "density_tier": "Podium / Wrap (25-45 u/acre)",
    "unit_size_sf": 850,
    "soft_cost_pct": 20.0,
}


def test_build_pdf_report_returns_valid_pdf_bytes(scored):
    selected = scored["metro"].tolist()[:3]
    compare_df = scored[scored["metro"].isin(selected)].set_index("metro").loc[selected]
    pdf_bytes = build_pdf_report(
        compare_df=compare_df, selected=selected,
        model_controls=_MODEL_CONTROLS, data_vintage="test-vintage",
    )
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_build_pdf_report_single_metro(scored):
    selected = [scored["metro"].iloc[0]]
    compare_df = scored[scored["metro"].isin(selected)].set_index("metro").loc[selected]
    pdf_bytes = build_pdf_report(
        compare_df=compare_df, selected=selected,
        model_controls=_MODEL_CONTROLS, data_vintage="test-vintage",
    )
    assert pdf_bytes.startswith(b"%PDF-")


def test_build_pdf_report_many_metros(scored):
    selected = scored["metro"].tolist()[:12]
    compare_df = scored[scored["metro"].isin(selected)].set_index("metro").loc[selected]
    pdf_bytes = build_pdf_report(
        compare_df=compare_df, selected=selected,
        model_controls=_MODEL_CONTROLS, data_vintage="test-vintage",
    )
    assert pdf_bytes.startswith(b"%PDF-")
