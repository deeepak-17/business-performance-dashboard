

import psycopg2
import pandas as pd

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "business_dw",
    "user": "deepak",
    "password": "postgres"
}

def run(conn, label, sql):
    print(f"\n{'='*60}")
    print(f"[QUERY] {label}")
    print('='*60)
    df = pd.read_sql(sql, conn)
    print(df.to_string(index=False))
    return df

def main():
    conn = psycopg2.connect(**DB_CONFIG)

    # KPI 1: Monthly Revenue Trend
    run(conn, "KPI 1 - Monthly Revenue Trend", """
        SELECT
            TO_CHAR(d.date_id, 'YYYY-MM')          AS month,
            COUNT(DISTINCT o.order_id)              AS total_orders,
            SUM(o.revenue)                          AS total_revenue,
            ROUND(AVG(o.revenue), 2)                AS avg_order_value,
            -- Month-over-month revenue change %
            ROUND(
                100.0 * (SUM(o.revenue) - LAG(SUM(o.revenue)) OVER (ORDER BY TO_CHAR(d.date_id, 'YYYY-MM')))
                / NULLIF(LAG(SUM(o.revenue)) OVER (ORDER BY TO_CHAR(d.date_id, 'YYYY-MM')), 0)
            , 2)                                    AS mom_growth_pct
        FROM fact_orders o
        JOIN dim_date d ON o.order_date = d.date_id
        WHERE o.status = 'completed'
        GROUP BY TO_CHAR(d.date_id, 'YYYY-MM')
        ORDER BY month;
    """)

    # KPI 2: Revenue by Product Category
    run(conn, "KPI 2 - Revenue by Product Category", """
        SELECT
            p.category,
            COUNT(o.order_id)       AS total_orders,
            SUM(o.revenue)          AS total_revenue,
            ROUND(100.0 * SUM(o.revenue) / SUM(SUM(o.revenue)) OVER (), 2) AS revenue_share_pct
        FROM fact_orders o
        JOIN dim_products p ON o.product_id = p.product_id
        WHERE o.status = 'completed'
        GROUP BY p.category
        ORDER BY total_revenue DESC;
    """)

    # KPI 3: Customer Lifetime Value (top 20)
    run(conn, "KPI 3 - Customer Lifetime Value (Top 20)", """
        SELECT
            c.customer_id,
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
        LIMIT 20;
    """)

    # KPI 4: Monthly Retention Cohorts
    run(conn, "KPI 4 - Monthly Retention Cohorts", """
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
        ORDER BY cohort_month, month_number
        LIMIT 50;
    """)

    # KPI 5: Top Products by Revenue + Running Total
    run(conn, "KPI 5 - Top Products with Running Revenue Total", """
        SELECT
            p.product_name,
            p.category,
            COUNT(o.order_id)                   AS units_sold,
            ROUND(SUM(o.revenue), 2)            AS total_revenue,
            ROUND(AVG(o.discount) * 100, 1)     AS avg_discount_pct,
            ROUND(SUM(SUM(o.revenue)) OVER (
                ORDER BY SUM(o.revenue) DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ), 2)                               AS running_total_revenue
        FROM fact_orders o
        JOIN dim_products p ON o.product_id = p.product_id
        WHERE o.status = 'completed'
        GROUP BY p.product_name, p.category
        ORDER BY total_revenue DESC;
    """)

    conn.close()
    print("\n\n[SUCCESS] All KPI queries ran successfully. Ready to connect Metabase!")

if __name__ == "__main__":
    main()