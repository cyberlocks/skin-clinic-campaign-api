"""
Skin Clinic Campaign Analysis API
----------------------------------
Exposes campaign response-rate analysis (Gender, Age Group,
Purchase Recency, Product Usage) as a FastAPI service.

Run locally:
    uvicorn main:app --reload

Endpoint:
    GET /campaign-analysis   -> JSON + HTML table view
    GET /                    -> health check
    GET /docs                -> interactive Swagger UI
"""

import os
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------
app = FastAPI(
    title="Skin Clinic Campaign Analysis API",
    description="Response-rate analysis of a skin clinic marketing campaign "
                 "across Gender, Age Group, Purchase Recency, and Product Usage.",
    version="1.0.0",
)

DATA_PATH = Path(__file__).parent / "data" / "skin_clinic_campaign.csv"


# ---------------------------------------------------------------------
# Data loading + analysis helpers
# ---------------------------------------------------------------------
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Data file not found at {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    required_cols = {
        "Gender",
        "AgeGroup",
        "Purchase_Last_Quarter",
        "Unique_Products_Purchased",
        "Response_to_Campaign",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing columns in dataset: {missing}")
    df["Responded"] = (df["Response_to_Campaign"] == "Yes").astype(int)
    return df


def bucket_products(n: int) -> str:
    if n <= 4:
        return "1-4"
    elif n <= 8:
        return "5-8"
    else:
        return ">8"


def response_table(df: pd.DataFrame, group_col: str, order: list[str] | None = None) -> list[dict]:
    g = df.groupby(group_col).agg(Total=("Responded", "size"), Responded=("Responded", "sum"))
    g["Response_Rate_%"] = (g["Responded"] / g["Total"] * 100).round(2)
    if order:
        g = g.reindex(order)
    g = g.reset_index().rename(columns={group_col: "Segment"})
    return g.to_dict(orient="records")


def build_analysis() -> dict:
    df = load_data()
    df["ProductBucket"] = df["Unique_Products_Purchased"].apply(bucket_products)

    return {
        "overall_response_rate_%": round(df["Responded"].mean() * 100, 2),
        "total_customers": int(len(df)),
        "gender_vs_response": response_table(df, "Gender", order=["Female", "Male"]),
        "age_group_vs_response": response_table(df, "AgeGroup", order=["<30", "30-50", ">50"]),
        "purchase_last_quarter_vs_response": response_table(
            df, "Purchase_Last_Quarter", order=["Yes", "No"]
        ),
        "product_usage_vs_response": response_table(
            df, "ProductBucket", order=["1-4", "5-8", ">8"]
        ),
    }


def _rows_to_html_table(rows: list[dict]) -> str:
    if not rows:
        return "<p>No data</p>"
    headers = rows[0].keys()
    thead = "".join(f"<th>{h}</th>" for h in headers)
    body_rows = ""
    for row in rows:
        cells = "".join(f"<td>{v}</td>" for v in row.values())
        body_rows += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{body_rows}</tbody></table>"


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Skin Clinic Campaign Analysis API is running."}


@app.get("/campaign-analysis")
def campaign_analysis_json():
    """Returns all four response-rate breakdowns as structured JSON."""
    return build_analysis()


@app.get("/campaign-analysis/table", response_class=HTMLResponse)
def campaign_analysis_html():
    """Returns the same analysis rendered as HTML tables for quick viewing in a browser."""
    analysis = build_analysis()

    sections = [
        ("Gender vs Campaign Response", analysis["gender_vs_response"]),
        ("Age Group vs Campaign Response", analysis["age_group_vs_response"]),
        ("Purchase in Last Quarter vs Campaign Response", analysis["purchase_last_quarter_vs_response"]),
        ("Product Usage vs Campaign Response", analysis["product_usage_vs_response"]),
    ]

    body = ""
    for title, rows in sections:
        body += f"<h2>{title}</h2>{_rows_to_html_table(rows)}"

    html = f"""
    <html>
    <head>
        <title>Skin Clinic Campaign Analysis</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
            h1 {{ margin-bottom: 4px; }}
            .subtitle {{ color: #666; margin-top: 0; margin-bottom: 30px; }}
            h2 {{ margin-top: 32px; }}
            table {{ border-collapse: collapse; width: 100%; max-width: 600px; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
            tr:nth-child(even) {{ background-color: #fafafa; }}
        </style>
    </head>
    <body>
        <h1>Skin Clinic Campaign Analysis</h1>
        <p class="subtitle">
            Total customers: {analysis['total_customers']} &nbsp;|&nbsp;
            Overall response rate: {analysis['overall_response_rate_%']}%
        </p>
        {body}
    </body>
    </html>
    """
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
