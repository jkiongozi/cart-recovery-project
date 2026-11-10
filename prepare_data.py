"""Turn the two Google Merchandise Store Excel files into clean data for the agent.

Run on its own (python prepare_data.py) to rebuild the files and print a summary,
or import load_carts() from the agent. This file replaces fetch_checkouts.py: no live data.

What it does, and why:
- One row per cart session. Sessions split across midnight are joined back together.
- Purchase history (previous_orders, lifetime_spend) is rebuilt from earlier sessions by the same visitor.
- Carts whose visitor bought in a later session are removed from the open list: nobody chases them.
- Ages are measured from the last day of the data, not today. Otherwise every cart is years old.
- 2016-17 is the only file the agent reviews. 2020-21 cart values are not reliable dollars
  (see data/data_quality_report.md), so that file is used for rates and comparison only.
- Visitor IDs, state and city are dropped here, so they can never reach the AI.
"""
import glob
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
CARTS_CSV = os.path.join(DATA_DIR, "open_carts.csv")
STATS_JSON = os.path.join(DATA_DIR, "dataset_stats.json")
REPORT_MD = os.path.join(DATA_DIR, "data_quality_report.md")

UA_RENAME = {"fullVisitorId": "visitor_id", "visitId": "session_id", "visit_date": "date",
             "visitNumber": "visit_number", "time_on_site_seconds": "time_on_site"}
GA4_RENAME = {"user_pseudo_id": "visitor_id", "ga_session_id": "session_id", "session_date": "date",
              "session_number": "visit_number", "session_duration_seconds": "time_on_site"}


def _find_excel(pattern):
    """Find a data file by name. Excel (.xlsx) or a CSV downloaded from BigQuery both work."""
    for ext in (".xlsx", ".csv"):
        found = sorted(glob.glob(os.path.join(BASE, pattern + ext)))
        if found:
            return found[0]
    raise SystemExit(f"Data file not found: a file named like {pattern}.xlsx or {pattern}.csv "
                     f"must be in {BASE}. See 'How to get the datasets' in README.md.")


def _read(path, rename):
    id_col = next(old for old, new in rename.items() if new == "visitor_id")
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path, dtype={id_col: str})
    else:
        # Use the sheet whose header has the ID column (the info sheet, if any, is skipped)
        book = pd.ExcelFile(path, engine="openpyxl")
        sheet = next((s for s in book.sheet_names
                      if id_col in book.parse(s, nrows=0).columns), None)
        if sheet is None:
            raise SystemExit(f"{os.path.basename(path)}: no sheet has a '{id_col}' column.")
        df = book.parse(sheet, dtype={id_col: str})
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"])
    df["transaction_revenue"] = df["transaction_revenue"].fillna(0.0)
    if "removed_from_cart" not in df:
        df["removed_from_cart"] = 0
    return df


def _join_midnight_splits(df):
    """Google records a visit that crosses midnight as two rows with the same IDs."""
    keys = ["visitor_id", "session_id"]
    if not df.duplicated(keys).any():
        return df, 0
    joined = df.sort_values("date").groupby(keys, as_index=False).agg(
        date=("date", "first"), visit_number=("visit_number", "first"),
        device_category=("device_category", "first"), traffic_source=("traffic_source", "first"),
        traffic_medium=("traffic_medium", "first"), pageviews=("pageviews", "sum"),
        time_on_site=("time_on_site", "sum"), added_to_cart=("added_to_cart", "max"),
        removed_from_cart=("removed_from_cart", "max"), reached_checkout=("reached_checkout", "max"),
        purchased=("purchased", "max"), products_added=("products_added", "sum"),
        added_product_value=("added_product_value", "sum"),
        transaction_revenue=("transaction_revenue", "max"))
    joined["abandoned"] = 1 - joined["purchased"]
    return joined, len(df) - len(joined)


def _add_history(df):
    """Facts from the same visitor's other sessions. Only sees what is inside the data window."""
    df = df.sort_values(["visitor_id", "date", "visit_number", "session_id"]).reset_index(drop=True)
    by = df.groupby("visitor_id", sort=False)
    df["previous_orders"] = (by["purchased"].cumsum() - df["purchased"]).astype(int)
    df["lifetime_spend"] = (by["transaction_revenue"].cumsum() - df["transaction_revenue"]).round(2)
    purchase_dates = df["date"].where(df["purchased"] == 1)
    next_purchase = purchase_dates.groupby(df["visitor_id"], sort=False).transform(lambda s: s.shift(-1).bfill())
    df["next_purchase_date"] = next_purchase
    return df


def _return_rate(df, days):
    """Share of abandoned carts whose visitor bought within N days with no recovery action.
    Carts too close to the end of the data are left out: they had less than N days to return."""
    last_day = df["date"].max()
    eligible = df[(df["abandoned"] == 1) & (df["date"] <= last_day - pd.Timedelta(days=days))]
    gap = (eligible["next_purchase_date"] - eligible["date"]).dt.days
    came_back = int((gap <= days).sum())
    return {"carts_with_full_window": len(eligible), "came_back": came_back,
            "rate_pct": round(came_back / len(eligible) * 100, 1) if len(eligible) else None}


def _stats(df, label, value_reliable):
    ab = df["abandoned"] == 1
    device = df.groupby("device_category")["abandoned"].agg(["size", "mean"])
    out = {
        "period": label,
        "first_day": str(df["date"].min().date()),
        "last_day": str(df["date"].max().date()),
        "cart_sessions": len(df),
        "purchased_sessions": int(df["purchased"].sum()),
        "abandoned_sessions": int(ab.sum()),
        "abandonment_rate_pct": round(ab.mean() * 100, 1),
        "reached_checkout_pct": round(df["reached_checkout"].mean() * 100, 1),
        "left_at_checkout_pct_of_checkouts": round(
            ((df["reached_checkout"] == 1) & ab).sum() / (df["reached_checkout"] == 1).sum() * 100, 1),
        "abandonment_rate_pct_by_device": {k: round(v * 100, 1) for k, v in device["mean"].items()},
        "cart_sessions_by_device": {k: int(v) for k, v in device["size"].items()},
        "came_back_and_bought_within_7_days": _return_rate(df, 7),
        "came_back_and_bought_within_30_days": _return_rate(df, 30),
        "cart_values_are_reliable_dollars": value_reliable,
    }
    if value_reliable:
        out["median_abandoned_cart"] = round(float(df.loc[ab, "added_product_value"].median()), 2)
        out["total_abandoned_value"] = round(float(df.loc[ab, "added_product_value"].sum()), 2)
    return out


MIN_SESSIONS = 100   # smaller groups are too noisy to act on


def _group_row(group, overall, has_value):
    rate = group["abandoned"].mean() * 100
    checkouts = group["reached_checkout"] == 1
    row = {"sessions": len(group),
           "abandoned": int(group["abandoned"].sum()),
           "abandonment_rate_pct": round(rate, 1),
           "points_vs_overall": round(rate - overall, 1),
           "reached_checkout_pct": round(checkouts.mean() * 100, 1),
           "left_at_checkout_pct_of_checkouts": (
               round((group.loc[checkouts, "abandoned"] == 1).mean() * 100, 1) if checkouts.any() else None)}
    if has_value:
        row["abandoned_value"] = round(float(group.loc[group["abandoned"] == 1, "added_product_value"].sum()), 2)
    return row


def _patterns(df, has_value):
    """Abandonment by group, across ALL cart sessions. Pageviews and time on site are left out on
    purpose: buying itself adds pages and minutes, so they would only appear to explain abandonment."""
    overall = df["abandoned"].mean() * 100
    groups = {
        "device": df["device_category"],
        "traffic_medium": df["traffic_medium"].astype(str),
        "visit_type": df["visit_number"].map(lambda n: "first visit" if n == 1 else "repeat visit"),
        "customer_type": df["previous_orders"].map(lambda n: "bought before" if n > 0 else "never bought"),
        "day_of_week": df["date"].dt.day_name(),
        "checkout_stage": df["reached_checkout"].map({1: "reached checkout", 0: "left before checkout"}),
    }
    if has_value:   # 2020-21 values and product counts are not reliable
        groups["cart_value"] = pd.cut(df["added_product_value"], [-1, 25, 50, 100, 200, float("inf")],
                                      labels=["$25 or less", "$25-50", "$50-100", "$100-200", "over $200"]).astype(str)
        groups["products_in_cart"] = pd.cut(df["products_added"], [0, 1, 3, float("inf")],
                                            labels=["1 product", "2-3 products", "4 or more"]).astype(str)
        groups["removed_items"] = df["removed_from_cart"].map({1: "removed an item", 0: "removed nothing"})
    out = {}
    for name, keys in groups.items():
        out[name] = {str(k): _group_row(g, overall, has_value)
                     for k, g in df.groupby(keys.values, observed=True) if len(g) >= MIN_SESSIONS}
    return out


def _value_check(df):
    """Compare what was added to the cart with what was paid, on purchased sessions."""
    paid = df[(df["purchased"] == 1) & (df["transaction_revenue"] > 0)]
    ratio = paid["added_product_value"] / paid["transaction_revenue"]
    return float(ratio.median()), float(((ratio >= 0.5) & (ratio <= 2)).mean() * 100), len(paid)


def build():
    print("Reading the Excel files (this can take up to a minute)...")
    ua_raw = _read(_find_excel("*2016_17*"), UA_RENAME)
    ga4_raw = _read(_find_excel("*GA4*"), GA4_RENAME)
    ua, ua_joined = _join_midnight_splits(ua_raw)
    ga4, _ = _join_midnight_splits(ga4_raw)
    ua, ga4 = _add_history(ua), _add_history(ga4)

    stats = {"2016-17": _stats(ua, "Aug 2016 - Aug 2017", True),
             "2020-21": _stats(ga4, "Nov 2020 - Jan 2021", False)}

    stats["2016-17"]["patterns"] = _patterns(ua, True)
    stats["2020-21"]["patterns"] = _patterns(ga4, False)

    as_of = ua["date"].max()
    ids = ua.sort_values(["date", "session_id"]).index
    ua.loc[ids, "cart_id"] = [f"UA-{n:05d}" for n in range(1, len(ids) + 1)]
    abandoned = ua[ua["abandoned"] == 1]
    returned = abandoned["next_purchase_date"].notna()
    carts = abandoned[~returned].copy()
    carts["days_since_abandoned"] = (as_of - carts["date"]).dt.days
    carts["created_at"] = carts["date"].dt.date.astype(str)
    carts = carts.rename(columns={"added_product_value": "cart_value", "products_added": "item_count"})
    keep = ["cart_id", "created_at", "days_since_abandoned", "cart_value", "item_count",
            "reached_checkout", "removed_from_cart", "device_category", "traffic_source",
            "traffic_medium", "pageviews", "time_on_site", "visit_number",
            "previous_orders", "lifetime_spend"]
    carts = carts[keep].sort_values("created_at", ascending=False)
    stats["2016-17"].update({"as_of_date": str(as_of.date()),
                             "abandoned_but_bought_in_a_later_session": int(returned.sum()),
                             "open_carts_for_review": len(carts)})

    os.makedirs(DATA_DIR, exist_ok=True)
    carts.to_csv(CARTS_CSV, index=False, encoding="utf-8")
    with open(STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    ua_ratio, ua_close, ua_paid = _value_check(ua)
    ga4_ratio, ga4_close, ga4_paid = _value_check(ga4)
    no_rev = int(((ga4_raw["purchased"] == 1) & (ga4_raw["transaction_revenue"] == 0)).sum())
    report = f"""# Data quality report

Built by prepare_data.py from the two Excel files.

## 2016-17 file: used for cart review
- Cart sessions in the file: {len(ua_raw):,}; after joining {ua_joined} sessions split across midnight: {len(ua):,}
- Abandoned: {len(abandoned):,}; visitor bought in a later session: {int(returned.sum()):,}; open carts for review: {len(carts):,}
- Cart value check on {ua_paid:,} paid sessions: value added to cart / amount paid has a median of {ua_ratio:.2f}, and {ua_close:.0f}% fall between half and double. Usable, but approximate.
- Cart value counts every add-to-cart, so repeated adds count twice and removed items are not taken off. {int(carts['removed_from_cart'].sum()):,} open carts had a removal.
- $0 carts in the open list: {int((carts['cart_value'] <= 0).sum())}
- Purchased sessions showing $0 revenue: {int(((ua['purchased'] == 1) & (ua['transaction_revenue'] == 0)).sum())}
- Sessions with no pageview count: {int(ua_raw['pageviews'].isna().sum())}; no time on site: {int(ua_raw['time_on_site'].isna().sum())}
- State shows "not available in demo dataset" on {int((ua_raw['state'] == 'not available in demo dataset').sum()):,} rows. State and city are not used.

## 2020-21 (GA4) file: rates and comparison only
- Cart value check on {ga4_paid:,} paid sessions: value added to cart / amount paid has a median of {ga4_ratio:.1f}, and only {ga4_close:.0f}% fall between half and double.
- Largest value in the file: ${ga4_raw['added_product_value'].max():,.0f}. The largest amount actually paid: ${ga4_raw['transaction_revenue'].max():,.0f}.
- The file comes from Google's obfuscated sample, and the median session shows {ga4_raw['products_added'].median():.0f} products added. Its cart values are not treated as dollars.
- Purchases with no revenue recorded: {no_rev}
- Traffic source is hidden on many rows ("(data deleted)" or "<Other>"): {int(ga4_raw['traffic_source'].isin(['(data deleted)', '<Other>']).sum()):,}

## Not in either file
Email address, email consent, product names, fabric, size, quantity, unit price, sale status, shipping and tax.

## Limits of purchase history
previous_orders and lifetime_spend only see inside each file's dates, and a visitor is a browser cookie. A customer on a new device looks new, so returning customers are undercounted.
"""
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    return carts, stats


def load_carts():
    """Return (carts as a list of dicts, stats). Rebuilds only when the clean files are missing."""
    stale = not (os.path.exists(CARTS_CSV) and os.path.exists(STATS_JSON))
    if not stale:
        with open(STATS_JSON, encoding="utf-8") as f:
            stale = "patterns" not in json.load(f)["2016-17"]   # built by an older version
    if stale:
        build()
    carts = pd.read_csv(CARTS_CSV, keep_default_na=False, na_values=[""],
                        dtype={"cart_id": str, "created_at": str})
    carts["pageviews"] = carts["pageviews"].astype(object).where(carts["pageviews"].notna(), None)
    carts["time_on_site"] = carts["time_on_site"].astype(object).where(carts["time_on_site"].notna(), None)
    with open(STATS_JSON, encoding="utf-8") as f:
        stats = json.load(f)
    return carts.to_dict("records"), stats


if __name__ == "__main__":
    carts, stats = build()
    for name, s in stats.items():
        print(f"\n===== {name} ({s['period']}) =====")
        print(f"Cart sessions:     {s['cart_sessions']:,}")
        print(f"Abandonment rate:  {s['abandonment_rate_pct']}%")
        print(f"Came back in 30d:  {s['came_back_and_bought_within_30_days']['rate_pct']}%")
    print(f"\nOpen carts for review: {len(carts):,} (value ${carts['cart_value'].sum():,.2f})")
    print(f"Saved to {DATA_DIR}: open_carts.csv, dataset_stats.json, data_quality_report.md")
