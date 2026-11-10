# Cart Recovery Agent

An AI agent that reviews abandoned carts from the Google Merchandise Store public data and recommends the cheapest action likely to recover each one, or says to leave it alone. It uses the same format and the same Jb Prints policies as CartGuard. It reads Excel files instead of live Shopify data.

The agent only **recommends**. No email is sent and no customer is contacted.

## Start here

Run these in the VS Code terminal in `C:\Users\Janeth\Cart_recovery`, with `.venv` active.

```powershell
pip install -r requirements.txt
Copy-Item ..\cart_abadndonment_agent\.env .env
python prepare_data.py
python agent.py
```

The second line reuses your OpenAI key. Only `OPENAI_API_KEY` is needed, and the Shopify lines in that file are ignored.

At `You:`, try:

- `Review my 5 most recent carts`
- `Review my 5 highest-value carts`
- `Summarize all my carts`
- `How does 2016-17 compare with 2020-21?`
- `How can I reduce cart abandonment?`

Type `quit` to stop. Each review is saved to `data/latest_review.md`.

| Command | What it does |
| --- | --- |
| `python prepare_data.py` | Rebuilds the clean data from the Excel files. Run it again after any change to this file or the Excel files |
| `python agent.py` | Starts the chat agent |
| `streamlit run dashboard.py` | Opens the dashboard |
| `streamlit run data_viewer.py` | Opens a page for browsing both datasets: filters, charts and the full table |
| `python risk.py` | Saves the rules baseline to `data/cart_recommendations.csv` |
| `python test_agent.py` | Runs the offline checks. Needs no API call |

## How to get the datasets

The project needs two files in the `Cart_recovery` folder. They are not on GitHub, so anyone who downloads the project has to add them.

| File | Period | Source in BigQuery |
| --- | --- | --- |
| A name containing `2016_17`, for example `Google_Merchandise_US_Cart_Sessions_2016_17.xlsx` | Aug 2016 to Aug 2017 | `bigquery-public-data.google_analytics_sample` |
| A name containing `GA4`, for example `Google Merchandise Store GA4 E-commerce Dataset.xlsx` | Nov 2020 to Jan 2021 | `bigquery-public-data.ga4_obfuscated_sample_ecommerce` |

Both are free public datasets from Google: anonymized Google Analytics data from the Google Merchandise Store, filtered to the United States and to sessions where something was added to the cart.

### Option A: ask for the Excel files

If you are a classmate or reviewer, ask Janeth for the two Excel files. Then skip to step 9 below.

### Option B: download them yourself from Google BigQuery

You need a Google account. The BigQuery sandbox is free and needs no credit card.

1. Go to [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery) and sign in with your Google account.
2. If asked, accept the terms and create a project (any name, for example `cart-recovery`). The free sandbox is enough.
3. Click the **+** tab (or **Compose new query**) to open a query editor.
4. In this project, open `sql/ua_2016_17.sql`, copy everything in it, and paste it into the editor.
5. Click **Run**. It takes up to a minute and returns about 33,700 rows.
6. Click **Save results** (or **Export**), then **CSV (local file)**.
7. Rename the downloaded file to `Google_Merchandise_US_Cart_Sessions_2016_17.csv`.
8. Repeat steps 3 to 7 with `sql/ga4_2020_21.sql`. It returns about 6,700 rows. Rename that file to `Google_Merchandise_GA4_2020_21.csv`.
9. Put both files in the `Cart_recovery` folder, next to `agent.py`. Excel (`.xlsx`) or CSV both work, as long as the names contain `2016_17` and `GA4`.
10. In the VS Code terminal, run:

```powershell
python prepare_data.py
```

It prints the number of cart sessions in each file and saves the clean data to the `data` folder.

### View the data

```powershell
streamlit run data_viewer.py
```

Your browser opens a page where you can switch between the two files, filter by date, outcome, device and traffic, see charts, and scroll or download the full table. Press Ctrl+C in the terminal to close it.

### Columns in the files

| Column | Meaning |
| --- | --- |
| `fullVisitorId` / `user_pseudo_id` | Anonymous browser ID |
| `visitId` / `ga_session_id` | Session ID |
| `visit_date` / `session_date` | Day of the session |
| `visitNumber` / `session_number` | 1 = first visit to the store |
| `state`, `city` | Location (not used by the agent) |
| `device_category` | desktop, mobile or tablet |
| `traffic_source`, `traffic_medium` | Where the visitor came from |
| `pageviews`, `time_on_site_seconds` / `session_duration_seconds` | Pages viewed and time spent |
| `added_to_cart`, `removed_from_cart`, `reached_checkout`, `purchased` | 1 = yes, 0 = no (`removed_from_cart` is 2016-17 only) |
| `products_added`, `added_product_value` | Products added and their value. Not reliable dollars in 2020-21 |
| `transaction_revenue` | Amount paid, if the session bought |
| `abandoned` | 1 = added to cart but did not buy in that session |

### If something goes wrong

| Message | Fix |
| --- | --- |
| `Data file not found` | A file is missing from the folder, or its name does not contain `2016_17` or `GA4` |
| `no sheet has a ... column` | The Excel file does not have the data columns. Use the file straight from BigQuery |
| BigQuery says you have exceeded a quota | The free sandbox allows 1 TB of queries a month; wait or use the Excel files |

## Recommendations to reduce abandonment

Ask `How can I reduce cart abandonment?` and the agent gives 3 to 5 store-wide ideas, saved to `data/latest_recommendations.md` and shown on the dashboard.

| Part | Who does it |
| --- | --- |
| Abandonment by device, traffic, visit type, customer type, day, checkout stage, cart value, products and removals | Python (`analyze_abandonment`), across all cart sessions |
| Choosing the biggest opportunities and writing the ideas | The AI |
| Adding the evidence figures | Python (`submit_recommendations`), so figures are never typed by the AI |
| Checks | Python refuses an idea with no real group behind it, or an offer other than the 5% and 10% in the policies |

Pageviews and time on site are left out of this analysis, because buying itself adds pages and minutes. The ideas are untested and show patterns in Google's data, not causes, so the agent never predicts how much abandonment will fall.

## What changed from CartGuard

| Part | CartGuard | Cart Recovery Agent |
| --- | --- | --- |
| Data | `fetch_checkouts.py`, live Shopify | `prepare_data.py`, two Excel files |
| Policies | `prompts/policies.md` | Same file, plus one simulation setting |
| Agent loop, tools, `submit_review`, profit math, five actions | Yes | Same |
| Rules baseline and dashboard | Yes | Same design |
| Product detail | Fabric, size, unit price | Not in the data; product count and cart value only |
| New facts for the AI | None | Device, traffic source, checkout stage, pageviews, time on site |
| New tools | None | `compare_datasets`, `analyze_abandonment`, `submit_recommendations` |
| Demo mode and Shopify files | Yes | Removed, since no live data is used |

Bug fixed here and still in CartGuard: a purchase rate typed on the `Free shipping:` line of `policies.md` was ignored, because the code stopped at the earlier `Free shipping threshold` line.

## How the data is prepared

| Step | Why |
| --- | --- |
| Join 19 sessions split across midnight | They are one visit |
| Rebuild `previous_orders` and `lifetime_spend` from earlier sessions by the same visitor | The policy needs to know who is a returning customer, and the file has no such field |
| Remove 3,674 abandoned carts whose visitor bought in a later session | They already came back |
| Count ages from August 1, 2017, the last day of the data | Counted from today, every cart would be years old and the answer would always be No action |
| Drop visitor IDs, state and city | Privacy policy: use only the data needed |

Result: **20,417 open carts worth $992,534.83**, with an average of $48.63 above $0.

## Simulated or assumed

- **Email consent is simulated.** The data has no email or consent field. `Assume carts are subscribed to email: yes` in `policies.md` treats every cart as subscribed. Set it to `no` and every email action is blocked, which leaves only No action and Escalate.
- **Jb Prints numbers are applied to Google's carts.** The 40% margin, $7 shipping and discount rules are your store's, not Google's. Profit figures show what your policies would do on these carts, not what Google earned.
- **Sale status is unknown.** The rule against discounts on sale items cannot be checked, so any discount carries a note to check first.

## Data problems

Full figures are in `data/data_quality_report.md`, written by `prepare_data.py`.

- **2020-21 cart values are not dollars.** On paid sessions, cart value is a median of 20 times the amount paid, and one value is $282 billion against a top payment of $865. That file gives rates and comparisons only, and the agent does not review its carts.
- **2016-17 cart values are approximate.** The median matches the amount paid, but only 62% of paid sessions fall between half and double. Repeated adds count twice and removed items are not taken off.
- **Returning customers are undercounted.** History covers 12 months, and a visitor is a browser cookie. Only 547 of the open carts count as returning, so few carts qualify for the 5% discount.

## What the data shows

| Measure | 2016-17 | 2020-21 |
| --- | --- | --- |
| Cart sessions | 33,706 | 6,746 |
| Abandonment rate | 71.5% | 81.2% |
| Reached checkout | 43.9% | 39.6% |
| Left at checkout, share of checkouts | 35.0% | 52.5% |
| Came back and bought within 30 days | 13.7% | 7.0% |

The periods are not like for like: 2020-21 covers only November to January. "Came back" is the closest thing here to a No action purchase rate. It is left as `?` in `policies.md` until you decide to use it. Neither file shows what a reminder, free shipping or a discount would do, because no such offers are recorded.

## Limitations

- Expected profit stays "unknown" and confidence stays Low until purchase rates are filled in.
- Risk is the model's judgment, not a trained prediction.
- One visitor can have several open carts, and each is reviewed separately.
