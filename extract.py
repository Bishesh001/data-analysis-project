# Loading the nine Olist CSV files into pandas DataFrames
from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(r"C:\Users\NIC\Desktop\Project- data analysis\archive (5)")

RAW_FILES = {
    "customers": "olist_customers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def find_data_dir():
    candidates = [PROJECT_DIR, Path.cwd(), Path.cwd() / "data" / "raw"]
    for folder in candidates:
        if all((folder / filename).exists() for filename in RAW_FILES.values()):
            return folder
    raise FileNotFoundError(
        "Could not find all nine Olist CSV files. Put them in PROJECT_DIR or the current folder: "
        + str(PROJECT_DIR)
    )


def load_all():
    data_dir = find_data_dir()
    tables = {}
    for name, filename in RAW_FILES.items():
        tables[name] = pd.read_csv(data_dir / filename, low_memory=False)
    return tables


if __name__ == "__main__":
    for name, df in load_all().items():
        print(f"{name:22} {df.shape[0]:>9,} rows x {df.shape[1]:>2} columns")
