import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from clean import clean_all
from extract import load_all


TABLE_ORDER = [
    "customers",
    "sellers",
    "products",
    "product_categories",
    "zip_locations",
    "orders",
    "order_items",
    "payments",
    "reviews",
]

DB_TABLES = {
    "payments": "order_payments",
    "reviews": "order_reviews",
}


def connection_url():
    required = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing database environment variables: {missing}")

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def load_database():
    engine = create_engine(connection_url())
    data = clean_all(load_all())
    schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

    try:
        with engine.begin() as conn:
            conn.execute(text(schema_sql))
            for name in TABLE_ORDER:
                table_name = DB_TABLES.get(name, name)
                data[name].to_sql(table_name, conn, if_exists="append", index=False, method="multi", chunksize=5000)
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
                print(f"{table_name:20s} loaded {count:>9,} rows")

            order_count = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one()
            item_orders = conn.execute(text("SELECT COUNT(DISTINCT order_id) FROM order_items")).scalar_one()
            print(f"orders={order_count:,}; orders with items={item_orders:,}")
    except SQLAlchemyError as exc:
        raise RuntimeError(f"PostgreSQL load failed and was rolled back: {exc}") from exc


if __name__ == "__main__":
    load_database()
