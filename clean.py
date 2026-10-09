# Cleaning and transformation 

import pandas as pd

from extract import load_all

# Two product categories used in products.csv are missing from the translation file.
# Their English names are literal translations of the Portuguese names.
EXTRA_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_and_food_preparers",
}


def pad_zip(series):
    """Zip prefixes were read as numbers, so '01037' became 1037. Restore 5 characters."""
    return series.astype(str).str.zfill(5)


def clean_city(series):
    """Lowercase, remove accents, keep only the city name when extra text was typed after it."""
    text = series.str.lower().str.replace("´", "'", regex=False)
    text = text.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")
    # 'sao paulo / sao paulo', 'sbc/sp', 'rio de janeiro, rio de janeiro, brasil' -> first part
    text = text.str.replace(r"\s*[/,\\(].*$", "", regex=True).str.strip()
    # Values that are not a usable city name cannot be repaired, so they become missing.
    unusable = text.str.fullmatch(r"\d+") | text.str.contains("@", regex=False) | (text.str.len() <= 2)
    return text.mask(unusable)


def clean_customers(raw):
    df = raw.copy()
    df["customer_zip_code_prefix"] = pad_zip(df["customer_zip_code_prefix"])
    df["customer_city"] = clean_city(df["customer_city"])
    return df


def clean_sellers(raw):
    df = raw.copy()
    df["seller_zip_code_prefix"] = pad_zip(df["seller_zip_code_prefix"])
    df["seller_city"] = clean_city(df["seller_city"])
    return df


def clean_orders(raw):
    df = raw.copy()
    date_columns = [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ]
    for column in date_columns:
        df[column] = pd.to_datetime(df[column])  # raises an error if a value cannot be parsed

    df["purchase_year_month"] = df["order_purchase_timestamp"].dt.strftime("%Y-%m")

    # Timestamps are kept as recorded. Orders whose steps are out of order are only flagged.
    df["has_date_order_issue"] = (
        (df["order_delivered_carrier_date"] < df["order_approved_at"])
        | (df["order_delivered_carrier_date"] < df["order_purchase_timestamp"])
        | (df["order_delivered_customer_date"] < df["order_delivered_carrier_date"])
    )

    # Delivery measures only make sense for delivered orders that have a delivery date.
    has_delivery = (df["order_status"] == "delivered") & df["order_delivered_customer_date"].notna()
    delivery_days = (df["order_delivered_customer_date"] - df["order_purchase_timestamp"]).dt.total_seconds() / 86400
    df["delivery_days"] = delivery_days.where(has_delivery)
    # The estimate is a date at midnight, so compare calendar dates, not full timestamps.
    delay = (df["order_delivered_customer_date"].dt.normalize() - df["order_estimated_delivery_date"].dt.normalize()).dt.days
    df["delay_days"] = delay.where(has_delivery).astype("Int64")
    df["is_late"] = df["delay_days"] > 0
    return df


def clean_order_items(raw):
    df = raw.copy()
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"])
    return df


def clean_payments(raw):
    # Nothing is changed: zero-value payments and 'not_defined' are real recorded states.
    return raw.copy()


def clean_reviews(raw):
    df = raw.copy()
    for column in ["review_creation_date", "review_answer_timestamp"]:
        df[column] = pd.to_datetime(df[column])
    # Comments that contain only spaces are empty comments.
    for column in ["review_comment_title", "review_comment_message"]:
        df[column] = df[column].mask(df[column].str.strip() == "")
    return df


def clean_products(raw):
    df = raw.rename(
        columns={"product_name_lenght": "product_name_length",
                 "product_description_lenght": "product_description_length"}
    )
    # A weight of 0 g is physically impossible, so it is treated as unknown.
    df["product_weight_g"] = df["product_weight_g"].mask(df["product_weight_g"] == 0)
    return df


def clean_categories(raw):
    extra = pd.DataFrame(
        {"product_category_name": list(EXTRA_TRANSLATIONS),
         "product_category_name_english": list(EXTRA_TRANSLATIONS.values())}
    )
    return pd.concat([raw, extra], ignore_index=True)


def build_zip_locations(raw_geolocation):
    """One row per zip prefix instead of up to 1,146 repeated coordinates."""
    geo = raw_geolocation
    # Rough bounding box of Brazil. Points outside it are wrong coordinates.
    in_brazil = geo["geolocation_lat"].between(-34, 5.3) & geo["geolocation_lng"].between(-74, -34)
    geo = geo[in_brazil]
    zip_locations = geo.groupby("geolocation_zip_code_prefix").agg(
        latitude=("geolocation_lat", "mean"),
        longitude=("geolocation_lng", "mean"),
        state=("geolocation_state", lambda states: states.mode().iloc[0]),
    ).reset_index()
    zip_locations["geolocation_zip_code_prefix"] = pad_zip(zip_locations["geolocation_zip_code_prefix"])
    return zip_locations.rename(columns={"geolocation_zip_code_prefix": "zip_code_prefix"})


def clean_all(raw):
    """Return a dict of cleaned DataFrames. Geolocation city text is dropped because it is inconsistent."""
    return {
        "customers": clean_customers(raw["customers"]),
        "sellers": clean_sellers(raw["sellers"]),
        "orders": clean_orders(raw["orders"]),
        "order_items": clean_order_items(raw["order_items"]),
        "payments": clean_payments(raw["payments"]),
        "reviews": clean_reviews(raw["reviews"]),
        "products": clean_products(raw["products"]),
        "product_categories": clean_categories(raw["category_translation"]),
        "zip_locations": build_zip_locations(raw["geolocation"]),
    }


if __name__ == "__main__":
    raw_tables = load_all()
    cleaned = clean_all(raw_tables)
    raw_names = {"product_categories": "category_translation", "zip_locations": "geolocation"}
    for name, df in cleaned.items():
        before = len(raw_tables[raw_names.get(name, name)])
        print(f"{name:20s} raw rows {before:>9,} -> clean rows {len(df):>9,}")
