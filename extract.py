from pathlib import Path
import pandas as pd

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "archive (5)"

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


ZIP_COLUMNS = {
    "customers": {"customer_zip_code_prefix": "string"},
    "sellers": {"seller_zip_code_prefix": "string"},
    "geolocation": {"geolocation_zip_code_prefix": "string"},
}


def find_data_dir(data_dir=None):
    if data_dir is not None:
        folder = Path(data_dir)
        missing = [filename for filename in RAW_FILES.values() if not (folder / filename).exists()]
        if missing:
            raise FileNotFoundError(f"Missing CSV files in {folder}: {missing}")
        return folder

    candidates = [DEFAULT_DATA_DIR, Path.cwd(), Path.cwd() / "archive (5)", Path.cwd() / "data" / "raw"]
    for folder in candidates:
        if all((folder / filename).exists() for filename in RAW_FILES.values()):
            return folder
    raise FileNotFoundError(
        "Could not find all nine Olist CSV files. Expected them in "
        f"{DEFAULT_DATA_DIR} or pass a folder to load_all(data_dir)."
    )


def load_all(data_dir=None):
    data_dir = find_data_dir(data_dir)
    tables = {}
    for name, filename in RAW_FILES.items():
        tables[name] = pd.read_csv(
            data_dir / filename,
            dtype=ZIP_COLUMNS.get(name),
            low_memory=False,
        )
    return tables


if __name__ == "__main__":
    for name, df in load_all().items():
        print(f"{name:22} {df.shape[0]:>9,} rows x {df.shape[1]:>2} columns")
