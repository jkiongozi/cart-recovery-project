"""Browse the two Google Merchandise Store Excel files.

Run:  streamlit run data_viewer.py
Opens in your web browser. Data stays on this computer.
dashboard.py shows the open carts and the agent's results; this page shows the full datasets.
"""
import pandas as pd
import streamlit as st

from prepare_data import GA4_RENAME, UA_RENAME, _find_excel, _read

DATASETS = {
    "2016-17 (Aug 2016 - Aug 2017)": ("*2016_17*.xlsx", UA_RENAME, True),
    "2020-21 (Nov 2020 - Jan 2021)": ("*GA4*.xlsx", GA4_RENAME, False),
}

st.set_page_config(page_title="Dataset Viewer", page_icon="📊", layout="wide")


@st.cache_data(show_spinner="Reading the Excel file (this can take up to a minute)...")
def load(name):
    pattern, rename, _ = DATASETS[name]
    path = _find_excel(pattern)
    df = _read(path, rename)
    df["outcome"] = df["purchased"].map({1: "Purchased", 0: "Abandoned"})
    notes = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
    return df, "\n".join(str(v) for v in notes[0].dropna())


def rate_by(df, column, top=10):
    """Sessions and abandonment rate for each value of a column, largest groups first."""
    out = df.groupby(column)["abandoned"].agg(sessions="size", rate="mean")
    out["Abandonment rate %"] = (out["rate"] * 100).round(1)
    return out.sort_values("sessions", ascending=False).head(top).drop(columns="rate")


st.title("📊 Google Merchandise Store Datasets")

with st.sidebar:
    st.header("Dataset")
    name = st.radio("Choose a file", list(DATASETS))

df_all, notes = load(name)
values_are_dollars = DATASETS[name][2]

with st.sidebar:
    st.header("Filters")
    first, last = df_all["date"].min().date(), df_all["date"].max().date()
    dates = st.date_input("Session date between", (first, last), min_value=first, max_value=last)
    outcome = st.multiselect("Outcome", ["Purchased", "Abandoned"], default=["Purchased", "Abandoned"])
    devices = sorted(df_all["device_category"].unique())
    device = st.multiselect("Device", devices, default=devices)
    mediums = sorted(df_all["traffic_medium"].astype(str).unique())
    medium = st.multiselect("Traffic medium", mediums, default=mediums)
    checkout_only = st.checkbox("Only sessions that reached checkout", value=False)

df = df_all[df_all["outcome"].isin(outcome) & df_all["device_category"].isin(device)
            & df_all["traffic_medium"].astype(str).isin(medium)]
if isinstance(dates, (list, tuple)) and len(dates) == 2:
    df = df[(df["date"].dt.date >= dates[0]) & (df["date"].dt.date <= dates[1])]
if checkout_only:
    df = df[df["reached_checkout"] == 1]

st.caption(f"{name} · United States · showing {len(df):,} of {len(df_all):,} cart sessions")
if not values_are_dollars:
    st.warning("Cart values in this file are not reliable dollars: on paid sessions they are a median of "
               "20 times the amount paid. Cart value charts are hidden here; the raw column stays in the table.")

overview, table, about = st.tabs(["Overview", "Full table", "About this file"])

with overview:
    if df.empty:
        st.info("No sessions match these filters.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cart sessions", f"{len(df):,}")
        c2.metric("Abandonment rate", f"{df['abandoned'].mean() * 100:.1f}%")
        c3.metric("Reached checkout", f"{df['reached_checkout'].mean() * 100:.1f}%")
        c4.metric("Revenue recorded", f"${df['transaction_revenue'].sum():,.2f}")

        st.subheader("Cart sessions per week")
        weekly = (df.set_index("date").resample("W")["outcome"].value_counts().unstack(fill_value=0))
        weekly.index = weekly.index.date
        st.bar_chart(weekly, y_label="Cart sessions")

        left, right = st.columns(2)
        with left:
            st.subheader("By device")
            st.dataframe(rate_by(df, "device_category"))
        with right:
            st.subheader("By traffic medium")
            st.dataframe(rate_by(df, "traffic_medium"))

        left, right = st.columns(2)
        with left:
            st.subheader("Top states")
            st.dataframe(rate_by(df, "state"))
        with right:
            if values_are_dollars:
                st.subheader("Cart value")
                bins = [-1, 0, 10, 25, 50, 100, 200, 500, float("inf")]
                labels = ["$0", "$0-10", "$10-25", "$25-50", "$50-100", "$100-200", "$200-500", "$500+"]
                sizes = pd.cut(df["added_product_value"], bins=bins, labels=labels)
                st.bar_chart(sizes.value_counts().reindex(labels).fillna(0).astype(int),
                             x_label="Cart value", y_label="Cart sessions")

with table:
    st.dataframe(df.drop(columns=["outcome"]), hide_index=True,
                 column_config={"date": st.column_config.DateColumn("date")})
    st.download_button("⬇️ Download these rows (CSV)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="cart_sessions.csv", mime="text/csv")

with about:
    st.text(notes)
