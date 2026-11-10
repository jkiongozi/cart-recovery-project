-- Source: Google Merchandise Store – Google Analytics 4 public BigQuery sample dataset
-- BigQuery Source:
-- bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
-- Period: November 1, 2020 – January 31, 2021
-- Geography: United States only
-- Unit of Analysis: One row represents one U.S. user shopping session in which at least one add_to_cart event occurred.
-- Number of Records: 6,746 cart sessions
-- How the Data Was Extracted:
-- The data was queried directly from Google BigQuery. Records were filtered to users with geo.country = 'United States'. GA4 event data was grouped by user_pseudo_id and ga_session_id to create one row per shopping session. Only sessions containing at least one add_to_cart event were retained.
-- Outcome Summary:
-- Cart sessions: 6,746
-- Purchased sessions: 1,268
-- Abandoned sessions: 5,478
-- Abandonment rate: 81.2%
-- Main Fields:
-- User/session ID, session date, session number, state, city, device category, traffic source, traffic medium, pageviews, session duration, add-to-cart indicator, checkout indicator, purchase indicator, number of products added, value of products added, transaction revenue, and abandoned-cart indicator.
-- Abandoned Cart Definition:
-- A session is classified as abandoned when the customer added at least one product to the cart but did not complete a purchase during that session.

WITH base AS (
  SELECT
    user_pseudo_id,
    (
      SELECT value.int_value
      FROM UNNEST(event_params)
      WHERE key = 'ga_session_id'
    ) AS ga_session_id,
    (
      SELECT value.int_value
      FROM UNNEST(event_params)
      WHERE key = 'ga_session_number'
    ) AS session_number,
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    event_timestamp,
    event_name,
    geo.region AS state,
    geo.city AS city,
    device.category AS device_category,
    traffic_source.source AS traffic_source,
    traffic_source.medium AS traffic_medium,
    ecommerce.purchase_revenue AS purchase_revenue,
    items
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE geo.country = 'United States'
),
session_summary AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    MIN(event_date) AS session_date,
    MAX(session_number) AS session_number,
    ANY_VALUE(state) AS state,
    ANY_VALUE(city) AS city,
    ANY_VALUE(device_category) AS device_category,
    ANY_VALUE(traffic_source) AS traffic_source,
    ANY_VALUE(traffic_medium) AS traffic_medium,
    COUNTIF(event_name = 'page_view') AS pageviews,
    ROUND(
      TIMESTAMP_DIFF(
        TIMESTAMP_MICROS(MAX(event_timestamp)),
        TIMESTAMP_MICROS(MIN(event_timestamp)),
        SECOND
      ),
0
    ) AS session_duration_seconds,
    MAX(IF(event_name = 'add_to_cart', 1, 0)) AS added_to_cart,
    MAX(IF(event_name = 'begin_checkout', 1, 0)) AS reached_checkout,
    MAX(IF(event_name = 'purchase', 1, 0)) AS purchased,
    MAX(
      IF(event_name = 'purchase', purchase_revenue, NULL)
    ) AS transaction_revenue
  FROM base
  WHERE ga_session_id IS NOT NULL
  GROUP BY
    user_pseudo_id,
    ga_session_id
),
cart_items AS (
  SELECT
    user_pseudo_id,
    ga_session_id,
    COUNT(DISTINCT item.item_id) AS products_added,
    SUM(
      COALESCE(item.price, 0)
      * COALESCE(item.quantity, 1)
    ) AS added_product_value
  FROM base
  CROSS JOIN UNNEST(items) AS item
  WHERE event_name = 'add_to_cart'
    AND ga_session_id IS NOT NULL
  GROUP BY
    user_pseudo_id,
    ga_session_id
)
SELECT
  s.user_pseudo_id,
  s.ga_session_id,
  s.session_date,
  s.session_number,
  s.state,
  s.city,
  s.device_category,
  s.traffic_source,
  s.traffic_medium,
  s.pageviews,
  s.session_duration_seconds,
  s.added_to_cart,
  s.reached_checkout,
  s.purchased,
  c.products_added,
  c.added_product_value,
  s.transaction_revenue,
  IF(s.purchased = 0, 1, 0) AS abandoned
FROM session_summary s
LEFT JOIN cart_items c
  USING (user_pseudo_id, ga_session_id)
WHERE s.added_to_cart = 1;
