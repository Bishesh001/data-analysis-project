import pandas as pd

from clean import clean_all
from extract import load_all


def print_table(title, table):
    print(f"\n{title}")
    print(table.to_string(index=False))


def run_analysis():
    data = clean_all(load_all())
    orders = data["orders"]
    payments = data["payments"]
    order_items = data["order_items"]
    products = data["products"]
    categories = data["product_categories"]
    customers = data["customers"]

    print_table("1. Orders by status", orders["order_status"].value_counts().rename_axis("status").reset_index(name="orders"))

    monthly = (
        orders.dropna(subset=["order_purchase_timestamp"])
        .assign(month=lambda df: df["order_purchase_timestamp"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)
        .size()
        .rename(columns={"size": "orders"})
    )
    print_table("2. Monthly order counts", monthly.tail(24))

    category_sales = (
        order_items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
        .merge(categories, on="product_category_name", how="left")
        .assign(category=lambda df: df["product_category_name_english"].fillna(df["product_category_name"]).fillna("unknown"))
        .groupby("category", as_index=False)
        .agg(items_sold=("order_item_id", "count"), item_sales=("price", "sum"), freight=("freight_value", "sum"))
        .sort_values("item_sales", ascending=False)
        .head(10)
    )
    print_table("3. Top product categories by item sales", category_sales)

    states = (
        customers["customer_state"]
        .value_counts()
        .rename_axis("state")
        .reset_index(name="customers")
        .head(10)
    )
    print_table("4. States with most customers", states)

    order_payment_totals = payments.groupby("order_id", as_index=False)["payment_value"].sum()
    print(f"\n5. Average order value from payments: {order_payment_totals['payment_value'].mean():.2f}")

    eligible = orders[
        (orders["order_status"] == "delivered")
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
    ]
    late_percentage = eligible["is_late"].mean() * 100
    print(f"\n6. Late delivered orders: {late_percentage:.2f}% of {len(eligible):,} eligible delivered orders")
    print(f"\n7. Average delivery duration: {eligible['delivery_days'].mean():.2f} days")

    payment_methods = (
        payments["payment_type"]
        .value_counts()
        .rename_axis("payment_type")
        .reset_index(name="payments")
    )
    print_table("8. Payment method distribution", payment_methods)


if __name__ == "__main__":
    run_analysis()
