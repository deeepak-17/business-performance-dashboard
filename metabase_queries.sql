
-- QUERY 1: Monthly Revenue Trend (Line Chart)
-- Chart type: Line | X-axis: month | Y-axis: total_revenue

SELECT
    TO_CHAR(d.date_id, 'YYYY-MM')          AS month,
    COUNT(DISTINCT o.order_id)              AS total_orders,
    ROUND(SUM(o.revenue), 2)               AS total_revenue,
    ROUND(AVG(o.revenue), 2)               AS avg_order_value,
    ROUND(
        100.0 * (SUM(o.revenue) - LAG(SUM(o.revenue)) OVER (ORDER BY TO_CHAR(d.date_id, 'YYYY-MM')))
        / NULLIF(LAG(SUM(o.revenue)) OVER (ORDER BY TO_CHAR(d.date_id, 'YYYY-MM')), 0)
    , 2)                                    AS mom_growth_pct
FROM fact_orders o
JOIN dim_date d ON o.order_date = d.date_id
WHERE o.status = 'completed'
GROUP BY TO_CHAR(d.date_id, 'YYYY-MM')
ORDER BY month;


-- QUERY 2: Revenue by Category (Bar Chart)
-- Chart type: Bar | X-axis: category | Y-axis: total_revenue

SELECT
    p.category,
    COUNT(o.order_id)       AS total_orders,
    ROUND(SUM(o.revenue), 2) AS total_revenue,
    ROUND(100.0 * SUM(o.revenue) / SUM(SUM(o.revenue)) OVER (), 2) AS revenue_share_pct
FROM fact_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.status = 'completed'
GROUP BY p.category
ORDER BY total_revenue DESC;


-- QUERY 3: Customer Lifetime Value (Table)
-- Chart type: Table | Shows top customers by lifetime value

SELECT
    c.name,
    c.segment,
    c.country,
    COUNT(o.order_id)               AS total_orders,
    ROUND(SUM(o.revenue), 2)        AS lifetime_value,
    ROUND(AVG(o.revenue), 2)        AS avg_order_value,
    RANK() OVER (ORDER BY SUM(o.revenue) DESC) AS clv_rank
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY c.customer_id, c.name, c.segment, c.country
ORDER BY lifetime_value DESC
LIMIT 50;


-- QUERY 4: Retention Cohorts (Table / Pivot)
-- Chart type: Table | Shows cohort retention rates

WITH first_purchase AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM fact_orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
monthly_activity AS (
    SELECT DISTINCT
        o.customer_id,
        DATE_TRUNC('month', o.order_date) AS activity_month
    FROM fact_orders o
    WHERE o.status = 'completed'
),
cohort_data AS (
    SELECT
        fp.cohort_month,
        ma.activity_month,
        COUNT(DISTINCT fp.customer_id) AS retained_customers,
        EXTRACT(EPOCH FROM (ma.activity_month - fp.cohort_month)) / (30*24*3600) AS month_number
    FROM first_purchase fp
    JOIN monthly_activity ma ON fp.customer_id = ma.customer_id
    GROUP BY fp.cohort_month, ma.activity_month
)
SELECT
    TO_CHAR(cohort_month, 'YYYY-MM')    AS cohort,
    month_number::INT                   AS months_since_first_purchase,
    retained_customers,
    ROUND(100.0 * retained_customers /
        FIRST_VALUE(retained_customers) OVER (
            PARTITION BY cohort_month ORDER BY month_number
        ), 2)                           AS retention_rate_pct
FROM cohort_data
ORDER BY cohort_month, month_number;


-- QUERY 5: Top Products (Bar Chart)
-- Chart type: Bar | X-axis: product_name | Y-axis: total_revenue

SELECT
    p.product_name,
    p.category,
    COUNT(o.order_id)                   AS units_sold,
    ROUND(SUM(o.revenue), 2)            AS total_revenue,
    ROUND(AVG(o.discount) * 100, 1)     AS avg_discount_pct
FROM fact_orders o
JOIN dim_products p ON o.product_id = p.product_id
WHERE o.status = 'completed'
GROUP BY p.product_name, p.category
ORDER BY total_revenue DESC;


-- QUERY 6: KPI Summary Cards
-- Create 3 separate Metabase "Metric" cards using these:

-- Total Revenue:
SELECT ROUND(SUM(revenue), 2) AS total_revenue FROM fact_orders WHERE status = 'completed';

-- Total Customers:
SELECT COUNT(DISTINCT customer_id) AS total_customers FROM fact_orders WHERE status = 'completed';

-- Avg Order Value:
SELECT ROUND(AVG(revenue), 2) AS avg_order_value FROM fact_orders WHERE status = 'completed';

-- Refund Rate %:
SELECT
    ROUND(100.0 * COUNT(CASE WHEN status = 'refunded' THEN 1 END) / COUNT(*), 2) AS refund_rate_pct
FROM fact_orders;