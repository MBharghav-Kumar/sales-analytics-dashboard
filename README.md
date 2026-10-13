# Sales Analytics Dashboard (Streamlit)

This project converts the supplied `pre.ipynb` sales-analysis workflow into an interactive Streamlit application.

## Included files

- `app.py` — dashboard and analysis pages
- `requirements.txt` — Python dependencies
- `.gitignore` — ignores local environments and secrets

## Features

- CSV upload and column-name normalization
- Date, region, category, and sales representative filters
- KPI overview: revenue, calculated profit/loss, profit margin, quantity, and row count
- Product/category ranking and high-volume low-margin checks
- Regional and sales representative performance
- Monthly/quarterly trends, month-over-month growth, daily revenue and 7-day rolling average, weekday/weekend comparison
- Customer segment and category analysis
- Discount band and discounted-vs-non-discounted comparisons
- Sales channel and payment method performance
- Correlation heatmap and relationship scatterplots
- Data quality report and CSV downloads

## Required CSV columns

The uploaded CSV should contain these columns (case and spaces are normalized):

- `Product_ID`
- `sale_date`
- `Sales_Rep`
- `Region`
- `sales_amount`
- `Quantity_sold`
- `Product_category`
- `unit_cost`
- `unit_price`
- `customer_type`
- `discount`
- `payment_method`
- `sales_channel`

`region_and_sales_rep` is optional and is not required by the dashboard. Common aliases such as `quantity` for `quantity_sold` and `category` for `product_category` are also accepted.

## Run locally

1. Install Python 3.10 or later.
2. Extract this ZIP file.
3. Open a terminal in the extracted folder.
4. Create and activate a virtual environment (optional but recommended).
5. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Start Streamlit:

   ```bash
   streamlit run app.py
   ```

7. Open the local URL shown in the terminal, usually `http://localhost:8501`.
8. Upload your CSV using the sidebar.

## Deploy on Streamlit Community Cloud

1. Put `app.py`, `requirements.txt`, and `.gitignore` in a GitHub repository.
2. Push the files to GitHub.
3. In Streamlit Community Cloud, create an app from that repository and choose `app.py` as the main file.
4. Deploy and upload the CSV in the running app.

Do not commit private datasets, API keys, Google credentials, or other secrets to a public repository.

## Profit calculation note

The supplied notebook calculates:

- `calculated_cogs = unit_cost * quantity_sold`
- `calculated_profit = sales_amount - calculated_cogs`
- `calculated_profit_margin = calculated_profit / sales_amount * 100`

The app preserves that formula. Confirm whether `sales_amount` already includes discounts and that `unit_cost`, `quantity_sold`, and sales revenue are consistent before relying on calculated profitability. The notebook reads from a Google Sheet, but this Streamlit app instead accepts a CSV upload so it can be deployed without Google authentication.

## Troubleshooting

- **Missing required columns:** compare the CSV header row to the required column list above.
- **Dates not appearing:** ensure `sale_date` contains parseable date values.
- **Empty charts after filtering:** reset or broaden filters in the sidebar.
- **Large files:** for very large CSV files, consider loading a sampled dataset or adding a database backend.
