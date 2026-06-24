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
    "profit":      "Profit",         # optional (profit/margin charts skip if None)
    "discount":    "Discount",       # optional (discount-vs-profit chart)
    "customer":    "Customer Name",  # optional (customer concentration)
    "category":    "Category",       # optional
    "subcategory": "Sub-Category",   # optional
    "product":     "Product Name",   # optional
    "region":      "Region",         # optional
}

ACCENT = "#2563eb"    # primary colour
ACCENT_2 = "#10b981"  # secondary (profit)
LOSS = "#ef4444"      # negative / loss

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
    for num in ("sales", "profit", "discount"):
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
has_discount = "discount" in df.columns and df["discount"].notna().any()
has_customer = "customer" in df.columns
has_product = "product" in df.columns


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
        return st.sidebar.multiselect(label, opts, default=opts)
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


# ──────────────────────────────────────────────────────────────────
# 6. KEY TAKEAWAYS  — computed live from the filtered data
# ──────────────────────────────────────────────────────────────────
DISC_BINS = [-0.001, 0, 0.10, 0.20, 0.30, 0.50, 1.0]
DISC_LABELS = ["0%", "1–10%", "11–20%", "21–30%", "31–50%", ">50%"]

def discount_profit(frame):
    f = frame.copy()
    f["disc_band"] = pd.cut(f["discount"], bins=DISC_BINS, labels=DISC_LABELS)
    return (f.groupby("disc_band", observed=True)["profit"]
              .mean().reset_index())

takeaways = []

# (a) discount threshold where average profit turns negative
if has_profit and has_discount:
    dp = discount_profit(data)
    neg_band = next((row["disc_band"] for _, row in dp.iterrows()
                     if row["profit"] < 0), None)
    if neg_band is not None:
        takeaways.append(
            f"Orders discounted at **{neg_band}** are, on average, "
            f"**unprofitable** — discounting past this point destroys margin.")
    else:
        takeaways.append("No discount band is unprofitable on average — "
                         "discounting is currently well-controlled.")

# (b) customer concentration (top 10%)
if has_customer:
    cust = data.groupby("customer")["sales"].sum().sort_values(ascending=False)
    n_top = max(1, (len(cust) + 9) // 10)  # ceil of 10%
    share = cust.head(n_top).sum() / cust.sum() * 100 if cust.sum() else 0
    takeaways.append(
        f"Your **top 10% of customers** ({n_top}) drive "
        f"**{share:.0f}%** of revenue.")

# (c) do bestsellers = top earners?
if has_profit and has_product:
    top_rev = set(data.groupby("product")["sales"].sum()
                      .sort_values(ascending=False).head(10).index)
    top_prof = set(data.groupby("product")["profit"].sum()
                       .sort_values(ascending=False).head(10).index)
    overlap = len(top_rev & top_prof)
    prod_profit = data.groupby("product")["profit"].sum()
    n_loss = int((prod_profit < 0).sum())
    takeaways.append(
        f"Only **{overlap} of your top 10 sellers** are also in the "
        f"top 10 by profit — revenue ≠ profit.")
    if n_loss:
        takeaways.append(
            f"**{n_loss} products** lose money overall (negative total profit).")

if takeaways:
    st.subheader("🔑 Key takeaways")
    st.info("\n\n".join(f"- {t}" for t in takeaways))

st.divider()


# ──────────────────────────────────────────────────────────────────
# 7. CHARTS
# ──────────────────────────────────────────────────────────────────
# 7a. Revenue (and profit) over time — monthly
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

# 7b. Sales by sub-category / category
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

# 7c. Margin by category — the "high sales, thin margin" contrast
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

# 7d. Discount vs profit — the signature insight
if has_profit and has_discount:
    dp = discount_profit(data)
    dp["sign"] = dp["profit"].apply(lambda v: "Profit" if v >= 0 else "Loss")
    fig_disc = px.bar(dp, x="disc_band", y="profit", color="sign",
                      title="Average profit per order by discount level",
                      color_discrete_map={"Profit": ACCENT_2, "Loss": LOSS},
                      category_orders={"disc_band": DISC_LABELS})
    fig_disc.update_layout(xaxis_title="Discount band", yaxis_title="Avg profit ($)",
                           legend_title_text="")
    fig_disc.add_hline(y=0, line_dash="dash", line_color="grey")
    st.plotly_chart(fig_disc, use_container_width=True)
    st.caption("Where the bars turn red, the average order at that discount "
               "level loses money.")

# 7e. Do bestsellers earn the most?  Top sellers + their actual profit
if has_profit and has_product:
    top_sellers = (data.groupby("product")
                       .agg(sales=("sales", "sum"), profit=("profit", "sum"))
                       .sort_values("sales", ascending=False).head(10)
                       .sort_values("sales", ascending=True).reset_index())
    top_sellers["short"] = top_sellers["product"].str.slice(0, 35) + "…"

    c1, c2 = st.columns(2)
    fig_rev = px.bar(top_sellers, x="sales", y="short", orientation="h",
                     title="Top 10 products by revenue",
                     color_discrete_sequence=[ACCENT])
    fig_rev.update_layout(yaxis_title="", xaxis_title="Sales ($)")
    c1.plotly_chart(fig_rev, use_container_width=True)

    top_sellers["sign"] = top_sellers["profit"].apply(
        lambda v: "Profit" if v >= 0 else "Loss")
    fig_pf = px.bar(top_sellers, x="profit", y="short", orientation="h",
                    color="sign", title="…and the profit those same sellers make",
                    color_discrete_map={"Profit": ACCENT_2, "Loss": LOSS})
    fig_pf.update_layout(yaxis_title="", xaxis_title="Profit ($)",
                         legend_title_text="")
    fig_pf.add_vline(x=0, line_dash="dash", line_color="grey")
    c2.plotly_chart(fig_pf, use_container_width=True)
    st.caption("Same products, sorted identically. If revenue meant profit, "
               "both charts would line up — watch the ones that shrink or go red.")

st.divider()

# 7f. Sales by region
if "region" in data.columns:
    by_reg = data.groupby("region")["sales"].sum().reset_index()
    fig_reg = px.bar(by_reg, x="region", y="sales", title="Sales by region",
                     color_discrete_sequence=[ACCENT])
    fig_reg.update_layout(xaxis_title="", yaxis_title="Sales ($)")
    st.plotly_chart(fig_reg, use_container_width=True)

with st.expander("View underlying data"):
    st.dataframe(data, use_container_width=True)
