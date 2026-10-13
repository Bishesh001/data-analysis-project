import pandas as pd

from extract import load_all


def pad_zip(series):
    return series.astype("string").str.extract(r"(\d+)", expand=False).str.zfill(5)


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
        df[column] = pd.to_datetime(df[column], errors="coerce")

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
        df[column] = df[column].mask(df[column].astype("string").str.strip() == "")
    return df


def clean_products(raw):
    df = raw.rename(
        columns={"product_name_lenght": "product_name_length",
                 "product_description_lenght": "product_description_length"}
    )
    # A weight of 0 g is physically impossible, so it is treated as unknown.
    df["product_weight_g"] = df["product_weight_g"].mask(df["product_weight_g"] == 0)
    return df


def clean_categories(raw, products=None):
    df = raw.drop_duplicates("product_category_name").copy()
    if products is not None:
        used_categories = set(products["product_category_name"].dropna())
        missing = sorted(used_categories - set(df["product_category_name"]))
        if missing:
            extra = pd.DataFrame({
                "product_category_name": missing,
                "product_category_name_english": missing,
            })
            df = pd.concat([df, extra], ignore_index=True)
    return df


def build_zip_locations(raw_geolocation):
    """One row per zip prefix instead of up to 1,146 repeated coordinates."""
    geo = raw_geolocation.copy()
    geo["geolocation_zip_code_prefix"] = pad_zip(geo["geolocation_zip_code_prefix"])
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
        "product_categories": clean_categories(raw["category_translation"], raw["products"]),
        "zip_locations": build_zip_locations(raw["geolocation"]),
    }


def validation_summary(raw, cleaned):
    checks = {
        "customers": ["customer_id"],
        "orders": ["order_id"],
        "order_items": ["order_id", "order_item_id"],
        "payments": ["order_id", "payment_sequential"],
        "reviews": ["review_id", "order_id"],
        "products": ["product_id"],
        "sellers": ["seller_id"],
        "product_categories": ["product_category_name"],
        "zip_locations": ["zip_code_prefix"],
    }
    raw_names = {"product_categories": "category_translation", "zip_locations": "geolocation"}
    lines = []
    for name, df in cleaned.items():
        before = len(raw[raw_names.get(name, name)])
        missing = df.isna().sum()
        missing = missing[missing > 0].sort_values(ascending=False).head(4)
        missing_text = ", ".join(f"{col}={count}" for col, count in missing.items()) or "none"
        key_cols = checks.get(name, [])
        duplicate_keys = df.duplicated(key_cols).sum() if key_cols else 0
        lines.append(
            f"{name:20s} raw={before:>9,} clean={len(df):>9,} "
            f"cols={df.shape[1]:>2} duplicate_keys={duplicate_keys:>5,} missing: {missing_text}"
        )
    return lines


if __name__ == "__main__":
    raw_tables = load_all()
    cleaned = clean_all(raw_tables)
    for line in validation_summary(raw_tables, cleaned):
        print(line)
