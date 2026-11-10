-- Source: Google Merchandise Store – Google Analytics 360 public sample dataset
-- BigQuery source: bigquery-public-data.google_analytics_sample.ga_sessions_*
-- Period: Aug 1, 2016 – Aug 1, 2017
-- Geography: United States only
-- Unit of analysis: One row = one user shopping session where at least one add-to-cart event occurred
-- Rows: 33,725 cart sessions
-- How extracted: Data was queried directly from Google BigQuery. Sessions were filtered to geoNetwork.country = 'United States'. Google Analytics ecommerce actions were used to identify add-to-cart, remove-from-cart, checkout and purchase activity. Product prices were converted from micros to dollars. Product impressions were excluded from the added-product-value calculation.
-- Main fields: Visitor/session ID, date, state/city, device, traffic source, pageviews, time on site, add/remove cart, checkout, purchase, number of products added, added product value, transaction revenue, and abandoned-cart indicator.

WITH session_level AS (
  SELECT
    s.fullVisitorId,
    s.visitId,
    PARSE_DATE('%Y%m%d', s.date) AS visit_date,
    s.visitNumber,
    -- Location
    s.geoNetwork.region AS state,
    s.geoNetwork.city AS city,
    -- Device
    s.device.deviceCategory AS device_category,
    -- Traffic source
    s.trafficSource.source AS traffic_source,
    s.trafficSource.medium AS traffic_medium,
    -- Session behavior
    s.totals.pageviews AS pageviews,
    s.totals.timeOnSite AS time_on_site_seconds,
    -- Ecommerce action flags
    MAX(
      IF(h.eCommerceAction.action_type = '3', 1, 0)
    ) AS added_to_cart,
    MAX(
      IF(h.eCommerceAction.action_type = '4', 1, 0)
    ) AS removed_from_cart,
    MAX(
      IF(h.eCommerceAction.action_type = '5', 1, 0)
    ) AS reached_checkout,
    MAX(
      IF(h.eCommerceAction.action_type = '6', 1, 0)
    ) AS purchased,
    -- Number of unique products actually added to cart
    COUNT(
      DISTINCT IF(
        h.eCommerceAction.action_type = '3'
        AND (p.isImpression IS NULL OR p.isImpression = FALSE),
        p.productSKU,
        NULL
      )
    ) AS products_added,
    -- Total value of products added to cart
    -- productPrice is stored in micros, so divide by 1,000,000
    SAFE_DIVIDE(
      SUM(
        IF(
          h.eCommerceAction.action_type = '3'
          AND (p.isImpression IS NULL OR p.isImpression = FALSE),
          CAST(COALESCE(p.productPrice, 0) AS NUMERIC),
          CAST(0 AS NUMERIC)
        )
      ),
      CAST(1000000 AS NUMERIC)
    ) AS added_product_value,
    -- Actual transaction revenue for completed purchases
    SAFE_DIVIDE(
      CAST(COALESCE(s.totals.transactionRevenue, 0) AS NUMERIC),
      CAST(1000000 AS NUMERIC)
    ) AS transaction_revenue
  FROM
    `bigquery-public-data.google_analytics_sample.ga_sessions_*` AS s
  CROSS JOIN
    UNNEST(s.hits) AS h
  LEFT JOIN
    UNNEST(h.product) AS p
  ON TRUE
  WHERE
    s.geoNetwork.country = 'United States'
    AND _TABLE_SUFFIX BETWEEN '20160801' AND '20170801'
  GROUP BY
    s.fullVisitorId,
    s.visitId,
    s.date,
    s.visitNumber,
    s.geoNetwork.region,
    s.geoNetwork.city,
    s.device.deviceCategory,
    s.trafficSource.source,
    s.trafficSource.medium,
    s.totals.pageviews,
    s.totals.timeOnSite,
    s.totals.transactionRevenue
)
SELECT
  *,
  IF(purchased = 0, 1, 0) AS abandoned
FROM session_level
WHERE added_to_cart = 1;
