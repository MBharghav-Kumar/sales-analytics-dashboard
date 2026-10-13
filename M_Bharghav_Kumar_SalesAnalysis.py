import io
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Sales Analytics Dashboard", page_icon="📊", layout="wide")

REQUIRED = [
    "product_id", "sale_date", "sales_rep", "region", "sales_amount",
    "quantity_sold", "product_category", "unit_cost", "unit_price",
    "customer_type", "discount", "payment_method", "sales_channel",
]
NUMERIC = ["sales_amount", "quantity_sold", "unit_cost", "unit_price", "discount"]

def normalize_name(name):
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())).strip("_")

def clean_numeric(series):
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.str.replace(r"[$,]", "", regex=True).str.replace("%", "", regex=False)
    cleaned = cleaned.replace({"": np.nan, "nan": np.nan, "None": np.nan, "—": np.nan, "-": np.nan})
    return pd.to_numeric(cleaned, errors="coerce")

# Public Google Sheet from the supplied notebook. The sheet must remain
# shared as "Anyone with the link can view" for the default data source to work.
DEFAULT_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/1gAJQrBFiLT-wF2mQ61RLH6UcXz_oM5la3HS2SeWOQZA/edit?usp=sharing"
)

@st.cache_data(ttl=300, show_spinner=False)
def load_default_sheet():
    return pd.read_csv(DEFAULT_SHEET_CSV_URL)

@st.cache_data(show_spinner=False)
def load_uploaded_file(file_bytes, file_name):
    if file_name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    return pd.read_csv(io.BytesIO(file_bytes))

def prepare_data(raw):
    df = raw.copy()
    df.columns = [normalize_name(c) for c in df.columns]
    # Accept common column-name variations
    aliases = {
        "quantity": "quantity_sold", "qty_sold": "quantity_sold",
        "category": "product_category", "sales_representative": "sales_rep",
        "region_sales_rep": "region_and_sales_rep",
    }
    df = df.rename(columns={c: aliases[c] for c in df.columns if c in aliases})
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return None, missing
    for c in NUMERIC:
        df[c] = clean_numeric(df[c])
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    for c in ["product_id", "sales_rep", "region", "product_category", "customer_type", "payment_method", "sales_channel"]:
        df[c] = df[c].astype("string").str.strip()
        df[c] = df[c].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    for c in ["region", "product_category", "payment_method", "customer_type", "sales_channel", "sales_rep"]:
        df[c] = df[c].str.title()
    df["calculated_cogs"] = df["unit_cost"] * df["quantity_sold"]
    df["calculated_profit"] = df["sales_amount"] - df["calculated_cogs"]
    df["calculated_profit_margin"] = np.where(
        df["sales_amount"].ne(0),
        df["calculated_profit"] / df["sales_amount"] * 100,
        np.nan,
    )
    # Notebook uses discounts as percentage values, e.g. 9 means 9%.
    df["discount_bin"] = pd.cut(
        df["discount"],
        bins=[-0.000001, 5, 10, 15, 20, 25, np.inf],
        labels=["0–5%", "5–10%", "10–15%", "15–20%", "20–25%", "25%+"],
        include_lowest=True,
    )
    df["is_discounted"] = df["discount"].fillna(0) > 0
    df["year_month"] = df["sale_date"].dt.to_period("M").astype("string")
    df["year"] = df["sale_date"].dt.year
    df["quarter"] = df["sale_date"].dt.to_period("Q").astype("string")
    df["weekday"] = df["sale_date"].dt.day_name()
    df["is_weekend"] = df["sale_date"].dt.dayofweek >= 5
    return df, []

def money(x):
    return f"${x:,.2f}" if pd.notna(x) else "N/A"

def metric_row(df):
    revenue = df["sales_amount"].sum()
    profit = df["calculated_profit"].sum()
    margin = (profit / revenue * 100) if revenue else np.nan
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Revenue", money(revenue))
    c2.metric("Calculated Profit / Loss", money(profit))
    c3.metric("Profit Margin", f"{margin:,.2f}%" if pd.notna(margin) else "N/A")
    c4.metric("Units Sold", f"{df['quantity_sold'].sum():,.0f}")
    c5.metric("Sales Records", f"{len(df):,}")

def aggregate(df, group, extra=None):
    agg = {
        "Revenue": ("sales_amount", "sum"),
        "Profit": ("calculated_profit", "sum"),
        "Units Sold": ("quantity_sold", "sum"),
        "Average Sale": ("sales_amount", "mean"),
        "Records": ("sales_amount", "count"),
    }
    if extra:
        agg.update(extra)
    out = df.groupby(group, dropna=False).agg(**agg).reset_index()
    out["Profit Margin (%)"] = np.where(out["Revenue"] != 0, out["Profit"] / out["Revenue"] * 100, np.nan)
    return out

st.title("📊 Sales Analytics Dashboard")
st.caption("Interactive sales dashboard. It loads your shared Google Sheet by default; upload another Excel or CSV file whenever you want to analyse a different dataset.")

with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Optional: upload a replacement file", type=["xlsx", "xls", "csv"])
    st.caption("By default, the dashboard loads your shared Google Sheet. Upload an Excel or CSV file to use different data instead.")
    page = st.radio(
        "Explore",
        ["Overview", "Product Analysis", "Regional & Sales Rep", "Time Trends",
         "Customer Analysis", "Discount Analysis", "Channels & Payments",
         "Correlation Analysis", "Data Quality & Raw Data"],
    )

if uploaded is None:
    try:
        with st.spinner("Loading the default sales dataset from Google Sheets..."):
            raw = load_default_sheet()
        st.sidebar.success("Using default Google Sheets data")
    except Exception as exc:
        st.error("The default Google Sheet could not be loaded. Check that the sheet is shared as 'Anyone with the link can view', or upload an Excel/CSV file in the sidebar.")
        st.caption(f"Technical detail: {exc}")
        st.stop()
else:
    try:
        raw = load_uploaded_file(uploaded.getvalue(), uploaded.name)
        st.sidebar.success(f"Using uploaded file: {uploaded.name}")
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")
        st.stop()

df, missing = prepare_data(raw)
if missing:
    st.error("This file is missing required columns: " + ", ".join(missing))
    st.write("Columns found:", list(raw.columns))
    st.markdown("See README.md for the expected columns and supported aliases.")
    st.stop()

with st.sidebar:
    st.divider()
    st.subheader("Filters")
    min_date = df["sale_date"].min()
    max_date = df["sale_date"].max()
    if pd.notna(min_date) and pd.notna(max_date):
        date_range = st.date_input("Sale date range", value=(min_date.date(), max_date.date()), min_value=min_date.date(), max_value=max_date.date())
    else:
        date_range = None
    regions = sorted(df["region"].dropna().unique().tolist())
    categories = sorted(df["product_category"].dropna().unique().tolist())
    reps = sorted(df["sales_rep"].dropna().unique().tolist())
    selected_regions = st.multiselect("Region", regions, default=regions)
    selected_categories = st.multiselect("Product category", categories, default=categories)
    selected_reps = st.multiselect("Sales representative", reps, default=reps)

filtered = df.copy()
if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    filtered = filtered[filtered["sale_date"].dt.date.between(date_range[0], date_range[1])]
if selected_regions:
    filtered = filtered[filtered["region"].isin(selected_regions)]
else:
    filtered = filtered.iloc[0:0]
if selected_categories:
    filtered = filtered[filtered["product_category"].isin(selected_categories)]
else:
    filtered = filtered.iloc[0:0]
if selected_reps:
    filtered = filtered[filtered["sales_rep"].isin(selected_reps)]
else:
    filtered = filtered.iloc[0:0]

if filtered.empty:
    st.warning("No rows match the selected filters. Adjust the filters in the sidebar.")
    st.stop()

st.caption(f"Showing {len(filtered):,} of {len(df):,} records after filters.")
if page == "Overview":
    metric_row(filtered)
    st.subheader("Revenue and calculated profit over time")
    monthly = filtered.dropna(subset=["sale_date"]).groupby("year_month", dropna=True).agg(
        Revenue=("sales_amount", "sum"), Profit=("calculated_profit", "sum")
    ).reset_index()
    if not monthly.empty:
        long = monthly.melt(id_vars="year_month", var_name="Metric", value_name="Amount")
        st.plotly_chart(px.line(long, x="year_month", y="Amount", color="Metric", markers=True, title="Monthly Revenue and Profit/Loss"), use_container_width=True)
    a, b = st.columns(2)
    with a:
        cat = aggregate(filtered, "product_category").sort_values("Revenue", ascending=False)
        st.plotly_chart(px.bar(cat, x="product_category", y="Revenue", title="Revenue by Product Category"), use_container_width=True)
    with b:
        reg = aggregate(filtered, "region").sort_values("Revenue", ascending=False)
        st.plotly_chart(px.bar(reg, x="region", y="Revenue", title="Revenue by Region"), use_container_width=True)
    st.subheader("Quick summary")
    st.dataframe(aggregate(filtered, "region").sort_values("Revenue", ascending=False), use_container_width=True)
    st.download_button("Download filtered data (CSV)", filtered.to_csv(index=False).encode("utf-8"), "filtered_sales_data.csv", "text/csv")

elif page == "Product Analysis":
    st.subheader("Product and category performance")
    top_n = st.slider("Number of products to display", 5, 30, 10)
    products = aggregate(filtered, "product_id").sort_values("Revenue", ascending=False)
    a, b = st.columns(2)
    with a:
        st.plotly_chart(px.bar(products.head(top_n).sort_values("Revenue"), x="Revenue", y="product_id", orientation="h", title=f"Top {top_n} Products by Revenue"), use_container_width=True)
    with b:
        qty = products.sort_values("Units Sold", ascending=False).head(top_n)
        st.plotly_chart(px.bar(qty.sort_values("Units Sold"), x="Units Sold", y="product_id", orientation="h", title=f"Top {top_n} Products by Quantity"), use_container_width=True)
    cats = aggregate(filtered, "product_category").sort_values("Revenue", ascending=False)
    st.plotly_chart(px.bar(cats, x="product_category", y="Profit", color="Profit Margin (%)", title="Calculated Profit/Loss by Category"), use_container_width=True)
    st.markdown("#### High-volume products with low/negative margins")
    threshold = products["Units Sold"].quantile(0.75)
    st.dataframe(products[(products["Units Sold"] >= threshold) & (products["Profit Margin (%)"] < 0)].sort_values("Profit Margin (%)"), use_container_width=True)
    st.dataframe(products.sort_values("Revenue", ascending=False), use_container_width=True)
    st.download_button("Download product summary", products.to_csv(index=False).encode(), "product_summary.csv", "text/csv")

elif page == "Regional & Sales Rep":
    st.subheader("Regional performance")
    region_summary = aggregate(filtered, "region").sort_values("Revenue", ascending=False)
    st.plotly_chart(px.bar(region_summary, x="region", y="Revenue", title="Revenue by Region"), use_container_width=True)
    st.plotly_chart(px.bar(region_summary, x="region", y="Profit", color="Profit Margin (%)", title="Calculated Profit/Loss by Region"), use_container_width=True)
    st.dataframe(region_summary, use_container_width=True)
    st.subheader("Sales representative performance")
    rep_summary = aggregate(filtered, "sales_rep").sort_values("Revenue", ascending=False)
    st.plotly_chart(px.bar(rep_summary, x="Revenue", y="sales_rep", orientation="h", title="Revenue by Sales Representative"), use_container_width=True)
    st.dataframe(rep_summary, use_container_width=True)
    st.subheader("Region × Category revenue")
    pivot = filtered.pivot_table(index="region", columns="product_category", values="sales_amount", aggfunc="sum", fill_value=0)
    st.plotly_chart(px.imshow(pivot, aspect="auto", title="Revenue Heatmap: Region vs Category", labels=dict(color="Revenue")), use_container_width=True)
    st.download_button("Download representative summary", rep_summary.to_csv(index=False).encode(), "sales_rep_summary.csv", "text/csv")

elif page == "Time Trends":
    st.subheader("Time-series analysis")
    dated = filtered.dropna(subset=["sale_date"]).copy()
    if dated.empty:
        st.warning("No valid dates found in sale_date.")
    else:
        monthly = dated.groupby("year_month").agg(Revenue=("sales_amount", "sum"), Profit=("calculated_profit", "sum"), Units=("quantity_sold", "sum"), Records=("sales_amount", "count")).reset_index()
        st.plotly_chart(px.line(monthly, x="year_month", y=["Revenue", "Profit"], markers=True, title="Monthly Revenue and Calculated Profit/Loss"), use_container_width=True)
        monthly["MoM Growth (%)"] = monthly["Revenue"].pct_change() * 100
        st.plotly_chart(px.bar(monthly.dropna(subset=["MoM Growth (%)"]), x="year_month", y="MoM Growth (%)", title="Month-over-Month Revenue Growth"), use_container_width=True)
        quarterly = dated.groupby("quarter").agg(Revenue=("sales_amount", "sum")).reset_index()
        st.plotly_chart(px.bar(quarterly, x="quarter", y="Revenue", title="Quarterly Revenue"), use_container_width=True)
        daily = dated.groupby(dated["sale_date"].dt.date).agg(Revenue=("sales_amount", "sum")).reset_index(names="sale_date").sort_values("sale_date")
        daily["7-day rolling average"] = daily["Revenue"].rolling(7, min_periods=1).mean()
        st.plotly_chart(px.line(daily, x="sale_date", y=["Revenue", "7-day rolling average"], title="Daily Revenue and 7-day Rolling Average"), use_container_width=True)
        weekday = dated.groupby("weekday").agg(Revenue=("sales_amount", "sum"), Average_Sale=("sales_amount", "mean"), Records=("sales_amount", "count")).reset_index()
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday["weekday"] = pd.Categorical(weekday["weekday"], categories=weekday_order, ordered=True)
        weekday = weekday.sort_values("weekday")
        st.plotly_chart(px.bar(weekday, x="weekday", y="Revenue", title="Revenue by Day of Week"), use_container_width=True)
        weekend = dated.groupby("is_weekend").agg(Revenue=("sales_amount", "sum"), Average_Sale=("sales_amount", "mean"), Records=("sales_amount", "count")).reset_index()
        weekend["Day Type"] = weekend["is_weekend"].map({True: "Weekend", False: "Weekday"})
        st.dataframe(weekend, use_container_width=True)
        st.dataframe(monthly, use_container_width=True)
        st.download_button("Download monthly trend", monthly.to_csv(index=False).encode(), "monthly_trend.csv", "text/csv")

elif page == "Customer Analysis":
    st.subheader("Customer segment performance")
    customer = aggregate(filtered, "customer_type", extra={"Average Discount (%)": ("discount", "mean")}).sort_values("Revenue", ascending=False)
    st.plotly_chart(px.bar(customer, x="customer_type", y="Revenue", title="Revenue by Customer Type"), use_container_width=True)
    st.plotly_chart(px.bar(customer, x="customer_type", y="Average Discount (%)", title="Average Discount by Customer Type"), use_container_width=True)
    st.dataframe(customer, use_container_width=True)
    st.subheader("Category preferences by customer type")
    cc = filtered.groupby(["customer_type", "product_category"], dropna=False).agg(Revenue=("sales_amount", "sum"), Units=("quantity_sold", "sum")).reset_index()
    st.plotly_chart(px.bar(cc, x="customer_type", y="Revenue", color="product_category", barmode="group", title="Revenue by Customer Type and Category"), use_container_width=True)
    cp = filtered.pivot_table(index="customer_type", columns="payment_method", values="sales_amount", aggfunc="count", fill_value=0)
    st.plotly_chart(px.imshow(cp, aspect="auto", title="Payment Method Record Counts by Customer Type"), use_container_width=True)
    st.download_button("Download customer summary", customer.to_csv(index=False).encode(), "customer_summary.csv", "text/csv")

elif page == "Discount Analysis":
    st.subheader("Promotion and discount impact")
    disc = aggregate(filtered, "discount_bin").dropna(subset=["discount_bin"])
    st.plotly_chart(px.bar(disc, x="discount_bin", y="Revenue", title="Revenue by Discount Band"), use_container_width=True)
    st.plotly_chart(px.line(disc, x="discount_bin", y="Profit Margin (%)", markers=True, title="Calculated Profit Margin by Discount Band"), use_container_width=True)
    comparison = filtered.groupby("is_discounted").agg(Revenue=("sales_amount", "sum"), Average_Sale=("sales_amount", "mean"), Units=("quantity_sold", "sum"), Average_Units=("quantity_sold", "mean"), Profit=("calculated_profit", "sum"), Average_Profit=("calculated_profit", "mean"), Records=("sales_amount", "count")).reset_index()
    comparison["Transaction Type"] = comparison["is_discounted"].map({True: "Discounted", False: "Non-discounted"})
    comparison["Profit Margin (%)"] = np.where(comparison["Revenue"] != 0, comparison["Profit"] / comparison["Revenue"] * 100, np.nan)
    st.plotly_chart(px.bar(comparison, x="Transaction Type", y="Average_Units", title="Average Quantity: Discounted vs Non-discounted"), use_container_width=True)
    st.dataframe(comparison, use_container_width=True)
    st.subheader("Products with highest average discounts")
    prod_disc = filtered.groupby("product_id").agg(Average_Discount=("discount", "mean"), Discounted_Record_Share=("is_discounted", "mean"), Revenue=("sales_amount", "sum"), Profit=("calculated_profit", "sum")).reset_index().sort_values("Average_Discount", ascending=False)
    st.dataframe(prod_disc.head(20), use_container_width=True)
    st.download_button("Download discount summary", disc.to_csv(index=False).encode(), "discount_summary.csv", "text/csv")

elif page == "Channels & Payments":
    st.subheader("Sales channel performance")
    channel = aggregate(filtered, "sales_channel").sort_values("Revenue", ascending=False)
    payment = aggregate(filtered, "payment_method").sort_values("Revenue", ascending=False)
    a, b = st.columns(2)
    with a:
        st.plotly_chart(px.bar(channel, x="sales_channel", y="Revenue", title="Revenue by Sales Channel"), use_container_width=True)
        st.dataframe(channel, use_container_width=True)
    with b:
        st.plotly_chart(px.bar(payment, x="payment_method", y="Revenue", title="Revenue by Payment Method"), use_container_width=True)
        st.dataframe(payment, use_container_width=True)
    cat_channel = filtered.groupby(["sales_channel", "product_category"]).agg(Revenue=("sales_amount", "sum")).reset_index()
    st.plotly_chart(px.bar(cat_channel, x="sales_channel", y="Revenue", color="product_category", barmode="group", title="Category Revenue by Sales Channel"), use_container_width=True)
    for label, col in [("Payment method by region", "region"), ("Payment method by customer type", "customer_type")]:
        st.subheader(label)
        pivot = filtered.pivot_table(index=col, columns="payment_method", values="sales_amount", aggfunc="count", fill_value=0)
        st.plotly_chart(px.imshow(pivot, aspect="auto", title=label), use_container_width=True)
    st.download_button("Download channel summary", channel.to_csv(index=False).encode(), "channel_summary.csv", "text/csv")

elif page == "Correlation Analysis":
    st.subheader("Correlation and numerical relationships")
    corr_cols = [c for c in ["sales_amount", "quantity_sold", "unit_price", "unit_cost", "discount", "calculated_profit", "calculated_profit_margin"] if c in filtered.columns]
    corr = filtered[corr_cols].corr(numeric_only=True)
    st.plotly_chart(px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto", title="Pearson Correlation Matrix"), use_container_width=True)
    a, b = st.columns(2)
    with a:
        st.plotly_chart(px.scatter(filtered, x="quantity_sold", y="sales_amount", trendline="ols", title="Quantity Sold vs Sales Amount"), use_container_width=True)
        st.plotly_chart(px.scatter(filtered, x="unit_price", y="quantity_sold", trendline="ols", title="Unit Price vs Quantity Sold"), use_container_width=True)
    with b:
        st.plotly_chart(px.scatter(filtered, x="discount", y="calculated_profit_margin", trendline="ols", title="Discount vs Calculated Profit Margin"), use_container_width=True)
        st.plotly_chart(px.scatter(filtered, x="unit_cost", y="calculated_profit", trendline="ols", title="Unit Cost vs Calculated Profit/Loss"), use_container_width=True)
    st.caption("Correlation does not establish causation. Relationships may also be influenced by how sales_amount, unit_price, quantity, and discount are defined.")
    st.dataframe(corr, use_container_width=True)

elif page == "Data Quality & Raw Data":
    st.subheader("Data quality report")
    quality = pd.DataFrame({
        "Missing values": filtered.isna().sum(),
        "Missing (%)": (filtered.isna().mean() * 100).round(2),
        "Data type": filtered.dtypes.astype(str),
        "Unique values": filtered.nunique(dropna=True),
    })
    st.dataframe(quality, use_container_width=True)
    st.write("Duplicate rows in uploaded data:", int(raw.duplicated().sum()))
    st.write("Invalid/unparsed sale dates:", int(df["sale_date"].isna().sum()))
    for col in ["sales_amount", "unit_cost", "unit_price", "quantity_sold", "discount"]:
        if col in df:
            st.write(f"Negative values in **{col}**:", int((df[col] < 0).sum()))
    st.warning("Calculated profit follows the notebook formula: sales_amount − (unit_cost × quantity_sold). Confirm that sales_amount is net revenue and unit_cost/quantity use consistent units before treating this as accounting profit.")
    st.subheader("Filtered records")
    st.dataframe(filtered, use_container_width=True, height=420)
    st.download_button("Download filtered records (CSV)", filtered.to_csv(index=False).encode("utf-8"), "filtered_sales_data.csv", "text/csv")
    st.download_button("Download cleaned full dataset (CSV)", df.to_csv(index=False).encode("utf-8"), "cleaned_sales_data.csv", "text/csv")

st.divider()
st.caption("Profit figures are calculated estimates based on the uploaded fields, not verified accounting statements.")
