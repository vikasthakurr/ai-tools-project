"""
Synthetic Data Generator for E-Commerce Text-to-SQL Application
Generates realistic Indian e-commerce data and loads it into SQLite.

Usage:
    python import_data.py

Output:
    - Creates ecommerce.db with all tables and sample data
    - Generates CSV files in data/ folder (optional export)
"""

import sqlite3
import random
import os
import csv
from datetime import datetime, timedelta

# Seed for reproducibility
random.seed(42)

# ============================================================
# CONFIGURATION
# ============================================================
DB_PATH = "ecommerce.db"
DATA_DIR = "data"
SCHEMA_PATH = os.path.join("database", "schema.sql")  # Optional; uses inline schema if not found

# ============================================================
# REFERENCE DATA
# ============================================================

CATEGORIES = [
    (1, "Electronics", "Smartphones, laptops, gadgets and accessories"),
    (2, "Clothing", "Men's and women's apparel"),
    (3, "Books", "Fiction, non-fiction, and academic books"),
    (4, "Home & Kitchen", "Appliances, cookware, and home decor"),
    (5, "Sports & Fitness", "Gym equipment, sportswear, and accessories"),
    (6, "Beauty & Health", "Skincare, haircare, and health products"),
    (7, "Toys & Games", "Children's toys, board games, and puzzles"),
    (8, "Grocery", "Food items, beverages, and daily essentials"),
]

PRODUCTS_BY_CATEGORY = {
    1: [  # Electronics
        ("iPhone 15 Pro", 134900), ("Samsung Galaxy S24", 79999),
        ("MacBook Air M2", 114900), ("Dell XPS 15", 89990),
        ("Sony WH-1000XM5 Headphones", 29990), ("Apple AirPods Pro", 24900),
        ("iPad Air", 69900), ("Kindle Paperwhite", 13999),
    ],
    2: [  # Clothing
        ("Men's Cotton Shirt", 1299), ("Women's Kurti Set", 1599),
        ("Denim Jeans", 1999), ("Formal Blazer", 4999),
        ("Running Shoes Nike", 7499), ("Leather Belt", 899),
    ],
    3: [  # Books
        ("Atomic Habits", 499), ("The Psychology of Money", 399),
        ("Clean Code", 2999), ("System Design Interview", 1899),
        ("Sapiens", 599), ("Rich Dad Poor Dad", 399),
    ],
    4: [  # Home & Kitchen
        ("Prestige Pressure Cooker", 2499), ("Philips Air Fryer", 8999),
        ("Dyson V12 Vacuum", 42900), ("Milton Water Bottle", 599),
        ("Pigeon Non-Stick Pan", 899), ("Borosil Lunch Box", 749),
    ],
    5: [  # Sports & Fitness
        ("Yoga Mat", 1299), ("Dumbbell Set 20kg", 3499),
        ("Resistance Bands", 699), ("Cricket Bat SG", 4599),
        ("Football Nike", 2499), ("Fitbit Charge 5", 14999),
    ],
    6: [  # Beauty & Health
        ("Neutrogena Sunscreen", 599), ("L'Oreal Shampoo", 449),
        ("Vitamin D3 Supplements", 899), ("Face Wash Himalaya", 199),
        ("Protein Powder 1kg", 2499), ("Hair Oil Parachute", 149),
    ],
    7: [  # Toys & Games
        ("LEGO City Set", 3999), ("Monopoly Board Game", 1299),
        ("Remote Control Car", 1899), ("Rubik's Cube", 399),
        ("Chess Set Wooden", 999), ("UNO Card Game", 249),
    ],
    8: [  # Grocery
        ("Basmati Rice 5kg", 599), ("Tata Tea Premium 1kg", 449),
        ("Amul Butter 500g", 275), ("Maggi Noodles Pack of 12", 216),
        ("Saffola Oil 5L", 899), ("Sugar 5kg", 249),
    ],
}

INDIAN_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ayaan", "Krishna", "Ishaan", "Rohan", "Amit", "Rahul", "Vikram",
    "Priya", "Ananya", "Diya", "Isha", "Kavya", "Meera", "Neha",
    "Pooja", "Riya", "Sakshi", "Tanvi", "Shreya", "Aisha", "Nisha",
    "Raj", "Karan", "Nikhil", "Sanjay", "Deepak", "Manish", "Suresh",
    "Lakshmi", "Divya", "Sunita", "Geeta", "Anjali", "Simran", "Komal",
    "Harish", "Ganesh", "Prakash", "Mohan", "Ravi", "Sunil", "Vijay", "Akash",
]

INDIAN_LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Reddy",
    "Nair", "Iyer", "Joshi", "Mishra", "Tiwari", "Pandey", "Chopra",
    "Mehta", "Shah", "Desai", "Kulkarni", "Rao", "Pillai", "Menon",
    "Bhat", "Hegde", "Shetty", "Patil", "More", "Jadhav", "Deshpande",
    "Agarwal", "Bansal", "Goyal", "Jain", "Saxena", "Kapoor", "Malhotra",
]

INDIAN_CITIES = [
    ("Mumbai", "Maharashtra"), ("Delhi", "Delhi"),
    ("Bangalore", "Karnataka"), ("Hyderabad", "Telangana"),
    ("Chennai", "Tamil Nadu"), ("Pune", "Maharashtra"),
    ("Kolkata", "West Bengal"), ("Ahmedabad", "Gujarat"),
    ("Jaipur", "Rajasthan"), ("Lucknow", "Uttar Pradesh"),
    ("Chandigarh", "Punjab"), ("Indore", "Madhya Pradesh"),
    ("Nagpur", "Maharashtra"), ("Kochi", "Kerala"),
    ("Gurgaon", "Haryana"), ("Noida", "Uttar Pradesh"),
    ("Coimbatore", "Tamil Nadu"), ("Vadodara", "Gujarat"),
    ("Bhopal", "Madhya Pradesh"), ("Thiruvananthapuram", "Kerala"),
]

DEPARTMENTS = ["Sales", "Support", "Logistics", "Management", "Marketing"]
ROLES = {
    "Management": ["CEO", "CTO", "VP Operations", "Director"],
    "Sales": ["Sales Manager", "Senior Sales Executive", "Sales Executive", "Sales Associate"],
    "Support": ["Support Manager", "Senior Support Executive", "Support Executive"],
    "Logistics": ["Logistics Manager", "Warehouse Lead", "Delivery Coordinator"],
    "Marketing": ["Marketing Manager", "Digital Marketing Executive", "Content Specialist"],
}

PAYMENT_METHODS = ["upi", "credit_card", "debit_card", "net_banking", "cash_on_delivery", "wallet"]
PAYMENT_WEIGHTS = [40, 20, 15, 10, 10, 5]  # percentage distribution

ORDER_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
ORDER_STATUS_WEIGHTS = [10, 15, 20, 45, 10]

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def random_date(start_str, end_str):
    """Generate a random datetime between two dates."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return start + timedelta(days=random_days, seconds=random_seconds)


def format_datetime(dt):
    """Format datetime as string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_date(dt):
    """Format date only."""
    return dt.strftime("%Y-%m-%d")


def generate_email(first_name, last_name, domain="gmail.com"):
    """Generate a realistic email address."""
    patterns = [
        f"{first_name.lower()}.{last_name.lower()}@{domain}",
        f"{first_name.lower()}{random.randint(1, 99)}@{domain}",
        f"{first_name.lower()}_{last_name.lower()}@{domain}",
    ]
    return random.choice(patterns)


def generate_phone():
    """Generate Indian phone number."""
    return f"+91 {random.randint(70000, 99999)}-{random.randint(10000, 99999)}"


def generate_transaction_id():
    """Generate a fake transaction ID."""
    prefix = random.choice(["TXN", "PAY", "UPI", "NB"])
    return f"{prefix}{random.randint(100000000, 999999999)}"


def weighted_choice(options, weights):
    """Select from options based on weights."""
    return random.choices(options, weights=weights, k=1)[0]

# ============================================================
# DATA GENERATORS
# ============================================================

def generate_products():
    """Generate product records from predefined lists."""
    products = []
    product_id = 1
    for cat_id, items in PRODUCTS_BY_CATEGORY.items():
        for name, price in items:
            # Add some price variation
            actual_price = round(price * random.uniform(0.95, 1.05), 2)
            stock = random.randint(5, 500)
            created = format_datetime(random_date("2023-01-01", "2025-01-01"))
            desc = f"High quality {name.lower()} available for delivery across India."
            products.append((product_id, name, desc, actual_price, stock, cat_id, created))
            product_id += 1
    return products


def generate_customers(count=100):
    """Generate customer records with Indian names and cities."""
    customers = []
    used_emails = set()

    for i in range(1, count + 1):
        first = random.choice(INDIAN_FIRST_NAMES)
        last = random.choice(INDIAN_LAST_NAMES)

        # Ensure unique email
        email = generate_email(first, last)
        while email in used_emails:
            email = generate_email(first, last, random.choice(["gmail.com", "yahoo.com", "outlook.com"]))
        used_emails.add(email)

        phone = generate_phone()
        city, state = random.choice(INDIAN_CITIES)
        country = "India"
        created = format_datetime(random_date("2022-01-01", "2025-06-01"))

        customers.append((i, first, last, email, phone, city, state, country, created))
    return customers


def generate_employees(count=20):
    """Generate employee records with hierarchy."""
    employees = []
    used_emails = set()

    # First 4 are managers (no manager_id)
    manager_count = 4
    for i in range(1, count + 1):
        first = random.choice(INDIAN_FIRST_NAMES)
        last = random.choice(INDIAN_LAST_NAMES)

        email = generate_email(first, last, "shopease.com")
        while email in used_emails:
            email = generate_email(first, last, "shopease.com")
        used_emails.add(email)

        if i <= manager_count:
            dept = DEPARTMENTS[i - 1] if i <= len(DEPARTMENTS) else "Management"
            role = ROLES.get(dept, ["Manager"])[0]
            salary = round(random.uniform(80000, 150000), 0)
            manager_id = None
        else:
            dept = random.choice(DEPARTMENTS)
            available_roles = ROLES.get(dept, ["Executive"])
            role = random.choice(available_roles[1:]) if len(available_roles) > 1 else available_roles[0]
            salary = round(random.uniform(25000, 75000), 0)
            manager_id = random.randint(1, manager_count)

        hire_date = format_date(random_date("2020-01-01", "2025-01-01"))
        employees.append((i, first, last, email, dept, role, salary, hire_date, manager_id))
    return employees

def generate_orders(num_orders=500, num_customers=100, num_employees=20):
    """Generate order records."""
    orders = []
    for i in range(1, num_orders + 1):
        customer_id = random.randint(1, num_customers)
        employee_id = random.randint(1, num_employees)
        order_date = random_date("2024-01-01", "2025-06-20")
        status = weighted_choice(ORDER_STATUSES, ORDER_STATUS_WEIGHTS)

        city, _ = random.choice(INDIAN_CITIES)
        address = f"{random.randint(1, 500)}, {random.choice(['MG Road', 'Station Road', 'Park Street', 'Ring Road', 'Civil Lines', 'Nehru Nagar', 'Gandhi Chowk', 'Lal Bagh'])}"

        # total_amount will be calculated from order_items later
        orders.append({
            "id": i,
            "customer_id": customer_id,
            "employee_id": employee_id,
            "order_date": format_datetime(order_date),
            "status": status,
            "total_amount": 0,  # placeholder
            "shipping_address": address,
            "shipping_city": city,
            "shipping_country": "India",
        })
    return orders


def generate_order_items(orders, products):
    """Generate order items ensuring referential integrity and realistic totals."""
    order_items = []
    item_id = 1

    product_prices = {p[0]: p[3] for p in products}  # {product_id: price}
    num_products = len(products)

    for order in orders:
        # Each order has 1-5 items
        num_items = random.randint(1, 5)
        order_total = 0

        # Pick unique products for this order
        selected_products = random.sample(range(1, num_products + 1), min(num_items, num_products))

        for prod_id in selected_products:
            quantity = random.randint(1, 4)
            unit_price = product_prices[prod_id]
            discount = round(random.choice([0, 0, 0, 0.05, 0.1, 0.15, 0.2, 0.25]), 2)

            line_total = quantity * unit_price * (1 - discount)
            order_total += line_total

            order_items.append((item_id, order["id"], prod_id, quantity, unit_price, discount))
            item_id += 1

        # Update order total
        order["total_amount"] = round(order_total, 2)

    return order_items


def generate_payments(orders):
    """Generate payment records matching orders."""
    payments = []
    payment_id = 1

    for order in orders:
        # Skip some cancelled orders (30% of cancelled have no payment)
        if order["status"] == "cancelled" and random.random() < 0.3:
            continue

        method = weighted_choice(PAYMENT_METHODS, PAYMENT_WEIGHTS)

        # Payment date is same day or next day
        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")
        pay_dt = order_dt + timedelta(hours=random.randint(0, 24))
        payment_date = format_datetime(pay_dt)

        # Payment status based on order status
        if order["status"] == "cancelled":
            pay_status = random.choice(["refunded", "failed"])
        elif order["status"] == "pending":
            pay_status = random.choice(["pending", "completed"])
        else:
            pay_status = "completed"

        txn_id = generate_transaction_id() if method != "cash_on_delivery" else None

        payments.append((
            payment_id, order["id"], order["total_amount"],
            method, payment_date, pay_status, txn_id
        ))
        payment_id += 1

    return payments

# ============================================================
# DATABASE OPERATIONS
# ============================================================

def create_database():
    """Create database and tables from schema.sql."""
    # Remove existing database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Read and execute schema
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r") as f:
            schema_sql = f.read()
        # Remove the sample queries section (everything after "SAMPLE ANALYTICAL QUERIES")
        if "SAMPLE ANALYTICAL QUERIES" in schema_sql:
            schema_sql = schema_sql[:schema_sql.index("-- SAMPLE ANALYTICAL QUERIES")]
        cursor.executescript(schema_sql)
        print("Schema created from schema.sql")
    else:
        # Inline schema creation if file not found
        print(f"Warning: {SCHEMA_PATH} not found. Creating tables inline.")
        cursor.executescript(INLINE_SCHEMA)

    conn.commit()
    return conn


def insert_data(conn, products, customers, employees, orders, order_items, payments):
    """Insert all generated data into the database."""
    cursor = conn.cursor()

    # Insert categories
    cursor.executemany(
        "INSERT INTO categories (id, name, description) VALUES (?, ?, ?)",
        CATEGORIES
    )
    print(f"  Inserted {len(CATEGORIES)} categories")

    # Insert products
    cursor.executemany(
        "INSERT INTO products (id, name, description, price, stock_quantity, category_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        products
    )
    print(f"  Inserted {len(products)} products")

    # Insert customers
    cursor.executemany(
        "INSERT INTO customers (id, first_name, last_name, email, phone, city, state, country, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        customers
    )
    print(f"  Inserted {len(customers)} customers")

    # Insert employees
    cursor.executemany(
        "INSERT INTO employees (id, first_name, last_name, email, department, role, salary, hire_date, manager_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        employees
    )
    print(f"  Inserted {len(employees)} employees")

    # Insert orders
    order_tuples = [
        (o["id"], o["customer_id"], o["employee_id"], o["order_date"],
         o["status"], o["total_amount"], o["shipping_address"],
         o["shipping_city"], o["shipping_country"])
        for o in orders
    ]
    cursor.executemany(
        "INSERT INTO orders (id, customer_id, employee_id, order_date, status, total_amount, shipping_address, shipping_city, shipping_country) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        order_tuples
    )
    print(f"  Inserted {len(orders)} orders")

    # Insert order items
    cursor.executemany(
        "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, discount) VALUES (?, ?, ?, ?, ?, ?)",
        order_items
    )
    print(f"  Inserted {len(order_items)} order items")

    # Insert payments
    cursor.executemany(
        "INSERT INTO payments (id, order_id, amount, payment_method, payment_date, status, transaction_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        payments
    )
    print(f"  Inserted {len(payments)} payments")

    conn.commit()

def export_csv(products, customers, employees, orders, order_items, payments):
    """Export all data to CSV files for backup/portability."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Categories
    with open(os.path.join(DATA_DIR, "categories.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "description"])
        writer.writerows(CATEGORIES)

    # Products
    with open(os.path.join(DATA_DIR, "products.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "description", "price", "stock_quantity", "category_id", "created_at"])
        writer.writerows(products)

    # Customers
    with open(os.path.join(DATA_DIR, "customers.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "first_name", "last_name", "email", "phone", "city", "state", "country", "created_at"])
        writer.writerows(customers)

    # Employees
    with open(os.path.join(DATA_DIR, "employees.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "first_name", "last_name", "email", "department", "role", "salary", "hire_date", "manager_id"])
        writer.writerows(employees)

    # Orders
    with open(os.path.join(DATA_DIR, "orders.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "customer_id", "employee_id", "order_date", "status", "total_amount", "shipping_address", "shipping_city", "shipping_country"])
        for o in orders:
            writer.writerow([o["id"], o["customer_id"], o["employee_id"], o["order_date"],
                           o["status"], o["total_amount"], o["shipping_address"],
                           o["shipping_city"], o["shipping_country"]])

    # Order Items
    with open(os.path.join(DATA_DIR, "order_items.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "order_id", "product_id", "quantity", "unit_price", "discount"])
        writer.writerows(order_items)

    # Payments
    with open(os.path.join(DATA_DIR, "payments.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "order_id", "amount", "payment_method", "payment_date", "status", "transaction_id"])
        writer.writerows(payments)

    print(f"\n  CSV files exported to {DATA_DIR}/ folder")

def print_summary(conn):
    """Print a summary of loaded data."""
    cursor = conn.cursor()
    print("\n" + "=" * 50)
    print("DATABASE SUMMARY")
    print("=" * 50)

    tables = ["categories", "products", "customers", "employees", "orders", "order_items", "payments"]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:<15} : {count:>6} records")

    # Additional stats
    cursor.execute("SELECT SUM(total_amount) FROM orders WHERE status != 'cancelled'")
    revenue = cursor.fetchone()[0]
    print(f"\n  Total Revenue (non-cancelled): ₹{revenue:,.2f}")

    cursor.execute("SELECT AVG(total_amount) FROM orders WHERE status != 'cancelled'")
    avg_order = cursor.fetchone()[0]
    print(f"  Average Order Value: ₹{avg_order:,.2f}")

    cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
    active_customers = cursor.fetchone()[0]
    print(f"  Active Customers (placed orders): {active_customers}")

    print("=" * 50)


# ============================================================
# INLINE SCHEMA (fallback if schema.sql not found)
# ============================================================
INLINE_SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, description TEXT,
    price REAL NOT NULL CHECK(price >= 0),
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE, phone TEXT,
    city TEXT, state TEXT, country TEXT NOT NULL DEFAULT 'India',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE, department TEXT NOT NULL,
    role TEXT NOT NULL, salary REAL NOT NULL CHECK(salary >= 0),
    hire_date TEXT NOT NULL, manager_id INTEGER,
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL, employee_id INTEGER,
    order_date TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending',
    total_amount REAL NOT NULL DEFAULT 0,
    shipping_address TEXT, shipping_city TEXT, shipping_country TEXT,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    discount REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    payment_method TEXT NOT NULL,
    payment_date TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'pending',
    transaction_id TEXT UNIQUE,
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
"""

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    """Main entry point — generates data and loads into SQLite."""
    print("=" * 50)
    print("E-Commerce Data Generator")
    print("=" * 50)

    # Generate data
    print("\n[1/4] Generating synthetic data...")
    products = generate_products()
    customers = generate_customers(100)
    employees = generate_employees(20)
    orders = generate_orders(500, 100, 20)
    order_items = generate_order_items(orders, products)
    payments = generate_payments(orders)

    print(f"  Generated {len(products)} products")
    print(f"  Generated {len(customers)} customers")
    print(f"  Generated {len(employees)} employees")
    print(f"  Generated {len(orders)} orders")
    print(f"  Generated {len(order_items)} order items")
    print(f"  Generated {len(payments)} payments")

    # Create database
    print("\n[2/4] Creating database...")
    conn = create_database()

    # Insert data
    print("\n[3/4] Inserting data into SQLite...")
    insert_data(conn, products, customers, employees, orders, order_items, payments)

    # Export CSV
    print("\n[4/4] Exporting to CSV...")
    export_csv(products, customers, employees, orders, order_items, payments)

    # Summary
    print_summary(conn)

    conn.close()
    print(f"\nDone! Database saved to: {DB_PATH}")
    print(f"CSV files saved to: {DATA_DIR}/")


if __name__ == "__main__":
    main()
