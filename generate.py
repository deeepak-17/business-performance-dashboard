
import psycopg2
from psycopg2.extras import execute_batch
from faker import Faker
import random
from datetime import datetime, timedelta

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "business_dw",
    "user": "deepak",
    "password": "postgres"
}

fake = Faker()
random.seed(42)
Faker.seed(42)

# Connect to default database and create business_dw if it doesn't exist
def create_database():
    conn = psycopg2.connect(**{**DB_CONFIG, "database": "postgres"})
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'business_dw'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE business_dw")
        print("[SUCCESS] Created database: business_dw")
    else:
        print("[SUCCESS] Database already exists")
    conn.close()

# Database Schema Definition
SCHEMA_SQL = """
DROP TABLE IF EXISTS fact_orders CASCADE;
DROP TABLE IF EXISTS dim_customers CASCADE;
DROP TABLE IF EXISTS dim_products CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;

-- Dimension: Date
CREATE TABLE dim_date (
    date_id     DATE PRIMARY KEY,
    year        INT,
    quarter     INT,
    month       INT,
    month_name  VARCHAR(20),
    week        INT,
    day_of_week VARCHAR(10)
);

-- Dimension: Customers
CREATE TABLE dim_customers (
    customer_id     SERIAL PRIMARY KEY,
    name            VARCHAR(100),
    email           VARCHAR(100),
    country         VARCHAR(50),
    city            VARCHAR(50),
    segment         VARCHAR(20),   -- 'B2B' or 'B2C'
    signup_date     DATE
);

-- Dimension: Products
CREATE TABLE dim_products (
    product_id      SERIAL PRIMARY KEY,
    product_name    VARCHAR(100),
    category        VARCHAR(50),
    unit_price      NUMERIC(10,2)
);

-- Fact: Orders
CREATE TABLE fact_orders (
    order_id        SERIAL PRIMARY KEY,
    order_date      DATE REFERENCES dim_date(date_id),
    customer_id     INT REFERENCES dim_customers(customer_id),
    product_id      INT REFERENCES dim_products(product_id),
    quantity        INT,
    unit_price      NUMERIC(10,2),
    discount        NUMERIC(4,2),
    revenue         NUMERIC(10,2),
    status          VARCHAR(20)   -- 'completed', 'refunded', 'pending'
);

-- Indexes for fast analytics
CREATE INDEX idx_orders_date     ON fact_orders(order_date);
CREATE INDEX idx_orders_customer ON fact_orders(customer_id);
CREATE INDEX idx_orders_product  ON fact_orders(product_id);
"""

# Data Generation Functions
def generate_dates(start, end):
    rows = []
    cur = start
    while cur <= end:
        rows.append((
            cur,
            cur.year,
            (cur.month - 1) // 3 + 1,
            cur.month,
            cur.strftime("%B"),
            cur.isocalendar()[1],
            cur.strftime("%A")
        ))
        cur += timedelta(days=1)
    return rows

def generate_customers(n=2000):
    segments = ['B2B', 'B2C']
    countries = ['India', 'USA', 'UK', 'Germany', 'Australia', 'Canada', 'Singapore']
    rows = []
    start = datetime(2023, 1, 1)
    end   = datetime(2024, 12, 31)
    for _ in range(n):
        signup = fake.date_between(start_date=start, end_date=end)
        rows.append((
            fake.name(),
            fake.email(),
            random.choice(countries),
            fake.city(),
            random.choice(segments),
            signup
        ))
    return rows

def generate_products():
    catalogue = [
        ("Analytics Pro Subscription", "SaaS",        299.99),
        ("Data Pipeline Tool",         "SaaS",        199.99),
        ("CRM Starter",                "SaaS",         99.99),
        ("CRM Enterprise",             "SaaS",        499.99),
        ("Marketing Suite",            "SaaS",        149.99),
        ("Laptop Stand",               "Hardware",     49.99),
        ("Mechanical Keyboard",        "Hardware",    129.99),
        ("4K Monitor",                 "Hardware",    399.99),
        ("Consulting (hourly)",        "Services",    150.00),
        ("Onboarding Package",         "Services",    800.00),
        ("Data Training Course",       "Education",    79.99),
        ("SQL Masterclass",            "Education",    49.99),
    ]
    return catalogue

def generate_orders(n_customers, n_products, start, end, n_orders=50000):
    """Generate random order data with realistic distribution of statuses."""
    statuses = ['completed'] * 85 + ['refunded'] * 10 + ['pending'] * 5
    rows = []
    for _ in range(n_orders):
        order_date = fake.date_between(start_date=start, end_date=end)
        customer_id = random.randint(1, n_customers)
        product_id  = random.randint(1, n_products)
        quantity    = random.randint(1, 5)
        unit_price  = None  # fetched from product on insert
        discount    = round(random.choice([0, 0, 0, 0.05, 0.10, 0.15, 0.20]), 2)
        status      = random.choice(statuses)
        rows.append((order_date, customer_id, product_id, quantity, discount, status))
    return rows

# Main Execution
def main():
    create_database()

    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    print("[STEP 1/5] Creating schema...")
    cur.execute(SCHEMA_SQL)
    conn.commit()

    # Dates
    start = datetime(2023, 1, 1).date()
    end   = datetime(2024, 12, 31).date()
    print("[STEP 2/5] Inserting dates...")
    date_rows = generate_dates(start, end)
    execute_batch(cur,
        "INSERT INTO dim_date VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        date_rows, page_size=500)
    conn.commit()

    # Customers
    print("[STEP 3/5] Inserting 2,000 customers...")
    customer_rows = generate_customers(2000)
    execute_batch(cur,
        "INSERT INTO dim_customers (name,email,country,city,segment,signup_date) VALUES (%s,%s,%s,%s,%s,%s)",
        customer_rows, page_size=500)
    conn.commit()

    # Products
    print("[STEP 4/5] Inserting products...")
    products = generate_products()
    execute_batch(cur,
        "INSERT INTO dim_products (product_name,category,unit_price) VALUES (%s,%s,%s)",
        products, page_size=100)
    conn.commit()

    # Fetch product prices for revenue calculation
    cur.execute("SELECT product_id, unit_price FROM dim_products")
    price_map = {row[0]: row[1] for row in cur.fetchall()}

    # Orders
    print("[STEP 5/5] Inserting 50,000 orders (this takes ~30 seconds)...")
    order_rows = generate_orders(2000, len(products), start, end)
    final_orders = []
    for (order_date, customer_id, product_id, quantity, discount, status) in order_rows:
        unit_price = float(price_map[product_id])
        revenue = round(unit_price * quantity * (1 - discount), 2)
        if status == 'refunded':
            revenue = -revenue
        final_orders.append((order_date, customer_id, product_id, quantity, unit_price, discount, revenue, status))

    execute_batch(cur,
        """INSERT INTO fact_orders
           (order_date, customer_id, product_id, quantity, unit_price, discount, revenue, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        final_orders, page_size=1000)
    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM fact_orders")
    print(f"\n[SUCCESS] Done! {cur.fetchone()[0]:,} orders inserted.")
    cur.execute("SELECT COUNT(*) FROM dim_customers")
    print(f"[SUCCESS] {cur.fetchone()[0]:,} customers inserted.")

    cur.close()
    conn.close()
    print("\n[COMPLETE] Database ready. Now run: python kpi_queries.py to verify queries.")

if __name__ == "__main__":
    main()