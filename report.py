"""
PDF export for the Metro Comparison shortlist: a formal, printable report
covering every metro a user has added via "Add to Comparison" on the Metro
Breakdown tab, so findings from a working session can be saved, shared, or
attached to an underwriting package instead of living only in the browser.

Built with reportlab's platypus layer (Table/Paragraph flowables) rather
than low-level canvas drawing, so the layout reflows cleanly regardless of
how many metros are in the shortlist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_ACCENT = colors.HexColor("#1f4e79")
_LIGHT_ROW = colors.HexColor("#eef3f8")
_GRID = colors.HexColor("#c9d6e3")

_SHORTAGE_COMPONENTS = [
    ("Permit Gap", "z_permit_gap"),
    ("Vacancy Tightness", "z_vacancy_tightness"),
    ("Price-to-Income", "z_price_to_income"),
    ("Rent-Income Divergence", "z_rent_income_divergence"),
]

_FEASIBILITY_BREAKDOWN = [
    ("Land Cost / Unit", "land_cost_per_unit_usd", "usd"),
    ("Hard (Construction) Cost / Unit", "hard_cost_per_unit_usd", "usd"),
    ("Soft Costs / Unit", "soft_costs_usd", "usd"),
    ("Development Cost / Unit", "development_cost_per_unit_usd", "usd"),
    ("Supportable Value / Unit", "supportable_value_usd", "usd"),
    ("Feasibility Gap / Unit", "feasibility_gap_usd", "usd"),
]

_MARKET_FACTS = [
    ("Median Home Price", "median_home_price_usd", "usd"),
    ("Median Household Income", "median_household_income_usd", "usd"),
    ("Price-to-Income Ratio", "price_to_income", "ratio"),
    ("Cap Rate", "cap_rate_pct", "pct"),
    ("Permit Friction Index", "permit_velocity_index", "num"),
]

_SUMMARY_COLUMNS = [
    ("Rank", "rank", "rank"),
    ("Opportunity", "opportunity_score", "score"),
    ("Shortage", "shortage_score", "score"),
    ("Feasibility", "feasibility_score", "score"),
    ("Price/Income", "price_to_income", "ratio"),
    ("Median Home Price", "median_home_price_usd", "usd"),
    ("Feas. Gap/Unit", "feasibility_gap_usd", "usd"),
]


def _fmt(value, kind: str) -> str:
    if pd.isna(value):
        return "--"
    if kind == "usd":
        return f"${value:,.0f}"
    if kind == "pct":
        return f"{value:.2f}%"
    if kind == "ratio":
        return f"{value:.2f}×"
    if kind == "score":
        return f"{value:.1f}"
    if kind == "rank":
        return f"#{int(value)}"
    if kind == "z":
        return f"{value:+.2f}"
    return f"{value:,.0f}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], textColor=_ACCENT, fontSize=22),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Normal"], fontSize=11, textColor=colors.grey, spaceAfter=4),
        "h2": ParagraphStyle("ReportH2", parent=base["Heading2"], textColor=_ACCENT, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("ReportH3", parent=base["Heading3"], textColor=_ACCENT, spaceBefore=10, spaceAfter=4),
        "body": base["Normal"],
        "small": ParagraphStyle("ReportSmall", parent=base["Normal"], fontSize=8, textColor=colors.grey),
        "caption": ParagraphStyle("ReportCaption", parent=base["Normal"], fontSize=9, textColor=colors.grey, spaceAfter=8),
    }


def _metric_table(rows: list[tuple[str, str]], col_widths=(2.6 * inch, 2.6 * inch)) -> Table:
    data = [[label, value] for label, value in rows]
    t = Table(data, colWidths=list(col_widths))
    t.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _LIGHT_ROW]),
                ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.black),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    )
    return t


def _cover_page(story, styles, selected, model_controls, data_vintage, generated_at):
    story.append(Paragraph("Affordable Housing Opportunity Report", styles["title"]))
    story.append(Paragraph("Metro Comparison -- Site Selection Findings", styles["subtitle"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"Generated {generated_at}", styles["body"]))
    story.append(Paragraph(f"Data vintage: {data_vintage}", styles["body"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Metros covered in this report", styles["h3"]))
    bullet_rows = [[f"{i+1}.", m] for i, m in enumerate(selected)]
    bt = Table(bullet_rows, colWidths=[0.3 * inch, 4.5 * inch])
    bt.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 10.5), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(bt)

    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph("Model settings used for these scores", styles["h3"]))
    settings_rows = [
        ("Opportunity weighting", f"α (Shortage) = {model_controls['alpha']:.2f}  /  β (Feasibility) = {1 - model_controls['alpha']:.2f}"),
        ("AMI affordability tier", f"{model_controls['ami_tier_pct']:.0f}% AMI"),
        ("Zoning / density tier", model_controls["density_tier"]),
        ("Assumed unit size", f"{model_controls['unit_size_sf']:.0f} SF"),
        ("Soft costs", f"{model_controls['soft_cost_pct']:.0f}% of land + hard cost"),
    ]
    story.append(_metric_table(settings_rows, col_widths=(2.2 * inch, 3.2 * inch)))
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "This report reflects a single point-in-time snapshot of the model's settings and the "
            "dataset's current provenance mix (live / published / synthetic -- see the closing page). "
            "It is a screening aid, not a substitute for a full local pro forma.",
            styles["caption"],
        )
    )
    story.append(PageBreak())


def _summary_table_page(story, styles, compare_df, selected):
    story.append(Paragraph("Executive Summary: Side-by-Side Comparison", styles["h2"]))

    header_style = ParagraphStyle(
        "SummaryHeader", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.white,
    )
    cell_style = ParagraphStyle("SummaryCell", fontName="Helvetica", fontSize=8, leading=10)
    metro_style = ParagraphStyle("SummaryMetroCell", fontName="Helvetica-Bold", fontSize=8, leading=10)

    header = [Paragraph("Metro", header_style)] + [
        Paragraph(label, header_style) for label, _, _ in _SUMMARY_COLUMNS
    ]
    rows = [header]
    for metro in selected:
        row = compare_df.loc[metro]
        rows.append(
            [Paragraph(metro, metro_style)]
            + [Paragraph(_fmt(row[col], kind), cell_style) for _, col, kind in _SUMMARY_COLUMNS]
        )

    col_widths = [1.3 * inch] + [0.812 * inch] * len(_SUMMARY_COLUMNS)
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_ROW]),
                ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t)
    story.append(
        Paragraph(
            "Ranked out of the full national metro universe. See each metro's detail page "
            "for the full shortage/feasibility breakdown behind these scores.",
            styles["caption"],
        )
    )
    story.append(PageBreak())


def _metro_detail_section(story, styles, compare_df, metro):
    row = compare_df.loc[metro]
    story.append(Paragraph(f"{metro}", styles["h2"]))
    story.append(
        Paragraph(
            f"National Rank #{int(row['rank'])}  •  Opportunity Score {row['opportunity_score']:.1f}  "
            f"•  Shortage {row['shortage_score']:.1f}  •  Feasibility {row['feasibility_score']:.1f}",
            styles["subtitle"],
        )
    )

    story.append(Paragraph("Shortage components (z-scores)", styles["h3"]))
    shortage_rows = [(label, _fmt(row[col], "z")) for label, col in _SHORTAGE_COMPONENTS]
    story.append(_metric_table(shortage_rows))

    story.append(Paragraph("Feasibility cost breakdown ($/unit)", styles["h3"]))
    feas_rows = [(label, _fmt(row[col], kind)) for label, col, kind in _FEASIBILITY_BREAKDOWN]
    story.append(_metric_table(feas_rows))

    story.append(Paragraph("Key market data", styles["h3"]))
    market_rows = [(label, _fmt(row[col], kind)) for label, col, kind in _MARKET_FACTS]
    story.append(_metric_table(market_rows))

    story.append(Spacer(1, 0.1 * inch))


def _provenance_page(story, styles, data_vintage):
    story.append(Paragraph("Data Sources & Disclaimer", styles["h2"]))
    story.append(Paragraph(f"Data vintage: {data_vintage}", styles["body"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        Paragraph(
            "Every figure in this report carries one of three provenance levels: "
            "<b>live</b> (fetched from the source API this session), <b>published</b> "
            "(a real, publicly-published Census ACS statistic, not modeled, but not "
            "re-fetched live this run -- median home price, median household income, "
            "and the price-to-income ratio computed from them), or <b>synthetic</b> "
            "(a modeled estimate, used where no free metro-level public source exists: "
            "land cost, construction cost, cap rate, operating expenses, vacancy/"
            "collection loss, and permit velocity). See the app's Data Sources tab for "
            "the exact provenance of every field in this report.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "<b>Disclaimer:</b> This report is a screening aid for illustrative and "
            "educational purposes. It is not investment, financial, or legal advice. "
            "Feasibility-side inputs (land cost, construction cost, cap rate, operating "
            "expenses, vacancy/collection loss, and permit velocity) are synthetic "
            "estimates, not observed market data -- always validate with a full local "
            "pro forma before making a development decision.",
            styles["body"],
        )
    )


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.75 * inch, 0.5 * inch, "Affordable Housing Opportunity Explorer -- Metro Comparison Report")
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf_report(
    compare_df: pd.DataFrame,
    selected: list[str],
    model_controls: dict,
    data_vintage: str,
) -> bytes:
    """Build a formal PDF report covering every metro in `selected`.

    `compare_df` must be the scored dataframe indexed by metro name (as
    produced by `score_metros(...).set_index("metro")`), containing at
    least the shortage/feasibility/market columns this module reads.
    `model_controls` is a dict with keys alpha, ami_tier_pct, density_tier,
    unit_size_sf, soft_cost_pct -- the sidebar settings in effect when the
    report was generated, included so the numbers are reproducible.
    """
    styles = _styles()
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title="Affordable Housing Opportunity Report",
    )

    story = []
    _cover_page(story, styles, selected, model_controls, data_vintage, generated_at)
    _summary_table_page(story, styles, compare_df, selected)

    for i, metro in enumerate(selected):
        section = []
        _metro_detail_section(section, styles, compare_df, metro)
        story.append(KeepTogether(section))
        if i < len(selected) - 1:
            story.append(PageBreak())

    story.append(PageBreak())
    _provenance_page(story, styles, data_vintage)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
