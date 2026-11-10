# Cart Recovery Agent

An AI agent that reviews abandoned carts from the Google Merchandise Store public data and recommends the cheapest action likely to recover each one, or says to leave it alone. It applies the Jb Prints store policies in `prompts/policies.md` to this historical data as a simulation, and can also recommend store-wide ways to reduce abandonment.

The agent only **recommends**. No email is sent and no customer is contacted.

## Access this project and its data

The project and both datasets are on GitHub at [github.com/jkiongozi/cart-recovery-project](https://github.com/jkiongozi/cart-recovery-project). The repository is public, so anyone can view it.

### Just look at the data, without installing anything

1. Open [github.com/jkiongozi/cart-recovery-project](https://github.com/jkiongozi/cart-recovery-project).
2. Click one of the two Excel files:
   - `Google_Merchandise_US_Cart_Sessions_2016_17 (1).xlsx`: Aug 2016 to Aug 2017
   - `Google Merchandise Store GA4 E-commerce Dataset (1).xlsx`: Nov 2020 to Jan 2021
3. Click **Download raw file** (the download icon at the top right of the file) and open it in Excel. The first sheet explains the data and the second sheet holds it.
4. The `data` folder has the cleaned results, for example `data/open_carts.csv` (the open carts the agent reviews) and `data/data_quality_report.md`. Click a file to view it.

### Download the project and work on it

You need [Python 3.13](https://www.python.org/downloads/), [Git](https://git-scm.com/downloads) and [VS Code](https://code.visualstudio.com/). The AI agent also needs your own OpenAI API key; the data viewer and dashboard do not.

1. Open VS Code, then **Terminal**, then **New Terminal**.
2. Go to the folder where you want the project, for example your Documents folder:

```powershell
cd $HOME\Documents
```

3. Download the project:

```powershell
git clone https://github.com/jkiongozi/cart-recovery-project.git
cd cart-recovery-project
code .
```

   The last line opens the project in VS Code. Use the terminal in that window from now on.

4. Create a virtual environment and install the packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

   If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` and try again. You should see `(.venv)` at the start of the line.

5. Prepare the data (the Excel files are already in the folder):

```powershell
python prepare_data.py
```

6. Browse both datasets in your browser:

```powershell
streamlit run data_viewer.py
```

   Switch between the two files in the left sidebar, filter them, and download rows as CSV. Press Ctrl+C in the terminal to stop.

7. To use the AI agent, add your own OpenAI key (see **Start here** below, step 2), then run `python agent.py`.

Each time you come back, open the folder in VS Code and run `.\.venv\Scripts\Activate.ps1` before the other commands.

### Make changes and share them

To save changes to GitHub you must be added as a collaborator. Without that, you can still change your own copy.

**Owner (Janeth): add a collaborator**

1. On the repository page, click **Settings**, then **Collaborators**, then **Add people**.
2. Enter their GitHub username or email and click **Add**.
3. They accept the invitation from their email or from github.com/notifications.

**Collaborator: get the latest version, then save your changes**

```powershell
git pull
```

Run this before you start, so you have everyone's latest changes. When you are done:

```powershell
git add .
git commit -m "Describe what you changed"
git push
```

The first push may open a browser window to sign in to GitHub. If `git push` is refused because someone else pushed first, run `git pull` and then `git push` again.

Never commit a `.env` file: it holds a private API key. `.gitignore` already keeps it out.

## Start here

You need Python 3.13, an OpenAI API key with **All** permissions and credit on the account, and the two dataset files (see **How to get the datasets** below).

**1. Create a virtual environment and install the packages** (in the VS Code terminal, in the project folder)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` and try again.

**2. Add your OpenAI key**

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace `sk-your-key` with your own key, with no spaces or quotes. Never share or commit this file; `.gitignore` keeps it off GitHub.

**3. Prepare the data and start the agent**

```powershell
python prepare_data.py
python agent.py
```

At `You:`, try:

- `Review my 5 most recent carts`
- `Review my 5 highest-value carts`
- `Summarize all my carts`
- `How does 2016-17 compare with 2020-21?`
- `How can I reduce cart abandonment?`

Type `quit` to stop. Each review is saved to `data/latest_review.md`.

**Or ask in your browser:** run `streamlit run ask_agent.py` (or double-click `run_ask_agent.bat`). Click an example question in the sidebar or type your own. Each answer shows the data the agent used underneath it: the carts, the summary tables, the 2016-17 vs. 2020-21 comparison, or abandonment by group, with charts. Click **Start a new conversation** to clear it.

| Command | What it does |
| --- | --- |
| `python prepare_data.py` | Rebuilds the clean data from the Excel files. Run it again after any change to this file or the Excel files |
| `python agent.py` | Starts the chat agent |
| `streamlit run dashboard.py` | Opens the dashboard |
| `streamlit run ask_agent.py` | Ask the agent in your browser, with one-click example questions, and see the tables and charts behind each answer |
| `streamlit run data_viewer.py` | Opens a page for browsing both datasets: filters, charts and the full table |
| `python risk.py` | Saves the rules baseline to `data/cart_recommendations.csv` |
| `python test_agent.py` | Runs the offline checks. Needs no API call |

## How to get the datasets

The project needs two files in the project folder. Both are included in the GitHub repository; Option B explains how to rebuild them from Google's original data.

| File | Period | Source in BigQuery |
| --- | --- | --- |
| A name containing `2016_17`, for example `Google_Merchandise_US_Cart_Sessions_2016_17.xlsx` | Aug 2016 to Aug 2017 | `bigquery-public-data.google_analytics_sample` |
| A name containing `GA4`, for example `Google Merchandise Store GA4 E-commerce Dataset.xlsx` | Nov 2020 to Jan 2021 | `bigquery-public-data.ga4_obfuscated_sample_ecommerce` |

Both are free public datasets from Google: anonymized Google Analytics data from the Google Merchandise Store, filtered to the United States and to sessions where something was added to the cart.

### Option A: use the Excel files in the GitHub repository

Both Excel files are already in the repository, so if you downloaded the project with `git clone` you have them. Skip to step 10 below.

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
9. Put both files in the project folder, next to `agent.py`. Excel (`.xlsx`) or CSV both work, as long as the names contain `2016_17` and `GA4`.
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

## How the project is built

| Part | Files | Role |
| --- | --- | --- |
| Data | `prepare_data.py`, `agent_data.py` | Read the two dataset files, clean them, rebuild purchase history and save the open carts and statistics to `data/`. No decisions |
| Decide (AI) | `agent.py`, `prompts/cart_recovery_system_prompt.md` | The OpenAI model chooses which tools to call, judges each cart's risk, chooses the action, and writes store-wide recommendations |
| Facts and rules in code | `agent.py` | Profit math, totals, policy checks, evidence figures and the review table are done in Python, never by the model |
| Business rules | `prompts/policies.md` | Product cost, discount rules, shipping cost, email cost, purchase-rate estimates and the email simulation setting |
| Rules baseline | `risk.py` | Plain if-then rules the agent never sees; the dashboard compares the AI's choices with them |
| View | `dashboard.py`, `data_viewer.py` | Streamlit pages: open carts and AI results, and the full datasets |
| Checks | `test_agent.py` | Offline tests of the profit math, policies and privacy |
| Queries | `sql/` | The BigQuery queries that produce the dataset files |

**The agent loop** (`run_agent` in `agent.py`): send the conversation to the model, and if it asks for a tool, run that Python function and feed the result back. Repeat until it answers, capped at 25 steps. It calls the OpenAI API directly with `requests`; no agent framework.

### The agent's tools

All tools return facts. The model decides what they mean.

| Tool | What it returns |
| --- | --- |
| `list_abandoned_checkouts` | Open carts with value, products, age, device, traffic, checkout stage and purchase history |
| `summarize_all_carts` | Counts and dollar totals across all open carts, grouped by age, stage, device, customer type and value |
| `get_checkout`, `get_review_rows` | One cart, or several carts with their exact total |
| `get_store_policies` | The text of `prompts/policies.md` |
| `calculate_profit` | For one cart and each of the five actions: whether it is allowed, profit if recovered, and expected profit when the purchase rate is known |
| `submit_review` | Finishes a cart review: Python adds the facts, profit and totals, applies the policies and records each recommendation |
| `compare_datasets` | Abandonment, checkout and return rates for both periods |
| `analyze_abandonment` | Abandonment by group across all cart sessions |
| `submit_recommendations` | Finishes a store-wide answer: Python adds the evidence and checks the policies |

The five actions are: No action, Reminder email, Free shipping, 5% discount and Escalate for human review. Policies are enforced in code: email actions only for subscribed customers, the 5% discount only for returning customers, and no other discount. A purchase rate typed into `policies.md` is used automatically.

### Common problems

| Message | Fix |
| --- | --- |
| `OPENAI_API_KEY is missing from .env` | Check that `.env` is in the project folder and the key line has no spaces or quotes |
| `OpenAI error 401 ... Missing scopes: model.request` | The key is restricted. On platform.openai.com, under API Keys, set its permissions to **All** |
| `OpenAI error 401` (other) | The key is wrong or was revoked; create a new one |
| `OpenAI error 429` | No credit on the OpenAI account; add credit under Organization settings, Billing |

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
