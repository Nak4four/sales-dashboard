"""
Sales Performance Overview — Streamlit dashboard
================================================

Business question this answers:
    "Where is this business making money, where is it leaking,
     and what's driving the trend?"

Built for the classic "Sample - Superstore" dataset, but adaptable:
to use it on a different dataset, edit ONLY the COLUMNS mapping below
(point each logical field at the matching column name in your file).
Everything downstream reads from this mapping, so the charts don't
need to change.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Then either place "Sample - Superstore.csv" next to this file,
or upload any sales CSV through the sidebar uploader.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

# ──────────────────────────────────────────────────────────────────
# 1. CONFIG  — the ONLY part you change to use a different dataset
# ──────────────────────────────────────────────────────────────────
DATA_FILE = "Sample - Superstore.csv"   # default file looked for on disk
DATE_FORMAT = None                       # None = let pandas infer; or e.g. "%m/%d/%Y"

# Map logical field -> the column name in YOUR file.
# Optional fields can be set to None if your data doesn't have them.
COLUMNS = {
    "date":        "Order Date",     # required
    "order_id":    "Order ID",       # required (used to count orders)
    "sales":       "Sales",          # required
    "profit":      "Profit",         # optional (margin charts skip if None)
    "category":    "Category",       # optional
    "subcategory": "Sub-Category",   # optional
    "product":     "Product Name",   # optional
    "region":      "Region",         # optional
}

ACCENT = "#2563eb"   # primary colour
ACCENT_2 = "#10b981" # secondary (profit)

# ──────────────────────────────────────────────────────────────────
# 2. PAGE SETUP
# ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Sales Performance Overview",
                   page_icon="📊", layout="wide")

st.title("📊 Sales Performance Overview")
st.caption("Where is the business making money, where is it leaking, "
           "and what's driving the trend?")


# ──────────────────────────────────────────────────────────────────
# 3. LOAD DATA  (from disk, or an uploaded file)
# ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_data(source) -> pd.DataFrame:
    # Superstore ships in latin-1; fall back to utf-8 for other files.
    try:
        df = pd.read_csv(source, encoding="latin-1")
    except (UnicodeDecodeError, LookupError):
        if hasattr(source, "seek"):
            source.seek(0)
        df = pd.read_csv(source, encoding="utf-8")

    df = df.rename(columns={v: k for k, v in COLUMNS.items() if v})
    df["date"] = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    df = df.dropna(subset=["date"])
    for num in ("sales", "profit"):
        if num in df.columns:
            df[num] = pd.to_numeric(df[num], errors="coerce")
    return df


uploaded = st.sidebar.file_uploader("Upload a sales CSV (optional)", type="csv")

try:
    df = load_data(uploaded) if uploaded is not None else load_data(DATA_FILE)
except FileNotFoundError:
    st.info("No data found. Place **Sample - Superstore.csv** next to this "
            "file, or upload a CSV from the sidebar to begin.")
    st.stop()
except Exception as e:
    st.error(f"Couldn't read the data: {e}")
    st.stop()

has_profit = "profit" in df.columns and df["profit"].notna().any()


# ──────────────────────────────────────────────────────────────────
# 4. SIDEBAR FILTERS
# ──────────────────────────────────────────────────────────────────
st.sidebar.header("Filters")

min_d, max_d = df["date"].min().date(), df["date"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_d, max_d),
                                   min_value=min_d, max_value=max_d)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
else:
    start_d, end_d = min_d, max_d

def multiselect_filter(label, field):
    if field in df.columns:
        opts = sorted(df[field].dropna().unique())
        chosen = st.sidebar.multiselect(label, opts, default=opts)
        return chosen
    return None

region_sel = multiselect_filter("Region", "region")
cat_sel = multiselect_filter("Category", "category")

mask = (df["date"].dt.date >= start_d) & (df["date"].dt.date <= end_d)
if region_sel is not None:
    mask &= df["region"].isin(region_sel)
if cat_sel is not None:
    mask &= df["category"].isin(cat_sel)
data = df[mask]

if data.empty:
    st.warning("No rows match the current filters.")
    st.stop()


# ──────────────────────────────────────────────────────────────────
# 5. KPI CARDS  (with vs-previous-period deltas)
# ──────────────────────────────────────────────────────────────────
def period_metrics(frame):
    revenue = frame["sales"].sum()
    orders = frame["order_id"].nunique()
    profit = frame["profit"].sum() if has_profit else None
    margin = (profit / revenue * 100) if has_profit and revenue else None
    aov = (revenue / orders) if orders else 0
    return revenue, profit, margin, orders, aov

# Build an equal-length immediately-preceding period for comparison.
span = (pd.Timestamp(end_d) - pd.Timestamp(start_d))
prev_start = pd.Timestamp(start_d) - span - pd.Timedelta(days=1)
prev_end = pd.Timestamp(start_d) - pd.Timedelta(days=1)
prev_mask = (df["date"] >= prev_start) & (df["date"] <= prev_end)
if region_sel is not None:
    prev_mask &= df["region"].isin(region_sel)
if cat_sel is not None:
    prev_mask &= df["category"].isin(cat_sel)
prev = df[prev_mask]

rev, prof, marg, ords, aov = period_metrics(data)
p_rev, p_prof, p_marg, p_ords, p_aov = period_metrics(prev)

def pct_delta(curr, base):
    if base in (None, 0) or curr is None:
        return None
    return f"{(curr - base) / base * 100:+.1f}%"

cols = st.columns(5 if has_profit else 4)
cols[0].metric("Revenue", f"${rev:,.0f}", pct_delta(rev, p_rev))
if has_profit:
    cols[1].metric("Profit", f"${prof:,.0f}", pct_delta(prof, p_prof))
    cols[2].metric("Margin", f"{marg:.1f}%",
                   None if p_marg is None else f"{marg - p_marg:+.1f} pts")
    cols[3].metric("Orders", f"{ords:,}", pct_delta(ords, p_ords))
    cols[4].metric("Avg order value", f"${aov:,.0f}", pct_delta(aov, p_aov))
else:
    cols[1].metric("Orders", f"{ords:,}", pct_delta(ords, p_ords))
    cols[2].metric("Avg order value", f"${aov:,.0f}", pct_delta(aov, p_aov))

st.caption("Deltas compare the selected range with the immediately "
           "preceding period of equal length.")
st.divider()


# ──────────────────────────────────────────────────────────────────
# 6. CHARTS
# ──────────────────────────────────────────────────────────────────
# 6a. Revenue (and profit) over time — monthly
ts = (data.set_index("date")
          .resample("MS")
          .agg({"sales": "sum", **({"profit": "sum"} if has_profit else {})})
          .reset_index())
value_cols = ["sales"] + (["profit"] if has_profit else [])
fig_time = px.line(ts, x="date", y=value_cols, markers=True,
                   title="Revenue and profit over time (monthly)",
                   color_discrete_sequence=[ACCENT, ACCENT_2])
fig_time.update_layout(legend_title_text="", yaxis_title="$", xaxis_title="")
st.plotly_chart(fig_time, use_container_width=True)

left, right = st.columns(2)

# 6b. Sales by category / sub-category
if "subcategory" in data.columns:
    by_sub = (data.groupby("subcategory")["sales"].sum()
                  .sort_values(ascending=True).reset_index())
    fig_sub = px.bar(by_sub, x="sales", y="subcategory", orientation="h",
                     title="Sales by sub-category",
                     color_discrete_sequence=[ACCENT])
    fig_sub.update_layout(yaxis_title="", xaxis_title="Sales ($)")
    left.plotly_chart(fig_sub, use_container_width=True)
elif "category" in data.columns:
    by_cat = data.groupby("category")["sales"].sum().reset_index()
    fig_cat = px.bar(by_cat, x="category", y="sales", title="Sales by category",
                     color_discrete_sequence=[ACCENT])
    left.plotly_chart(fig_cat, use_container_width=True)

# 6c. Margin by category — the "high sales, thin margin" contrast
if has_profit and "category" in data.columns:
    m = data.groupby("category").agg(sales=("sales", "sum"),
                                     profit=("profit", "sum")).reset_index()
    m["margin"] = m["profit"] / m["sales"] * 100
    fig_marg = px.bar(m.sort_values("margin"), x="margin", y="category",
                      orientation="h", title="Profit margin by category (%)",
                      color="margin", color_continuous_scale="RdYlGn")
    fig_marg.update_layout(yaxis_title="", xaxis_title="Margin (%)",
                           coloraxis_showscale=False)
    right.plotly_chart(fig_marg, use_container_width=True)

# 6d. Top 10 products by revenue (concentration / Pareto)
if "product" in data.columns:
    top = (data.groupby("product")["sales"].sum()
               .sort_values(ascending=False).head(10)
               .sort_values(ascending=True).reset_index())
    fig_top = px.bar(top, x="sales", y="product", orientation="h",
                     title="Top 10 products by revenue",
                     color_discrete_sequence=[ACCENT])
    fig_top.update_layout(yaxis_title="", xaxis_title="Sales ($)")
    st.plotly_chart(fig_top, use_container_width=True)

# 6e. Sales by region
if "region" in data.columns:
    by_reg = data.groupby("region")["sales"].sum().reset_index()
    fig_reg = px.bar(by_reg, x="region", y="sales", title="Sales by region",
                     color_discrete_sequence=[ACCENT])
    fig_reg.update_layout(xaxis_title="", yaxis_title="Sales ($)")
    st.plotly_chart(fig_reg, use_container_width=True)

st.divider()
with st.expander("View underlying data"):
    st.dataframe(data, use_container_width=True)
