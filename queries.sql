-- 1. Order counts by status
SELECT order_status, COUNT(*) AS orders
FROM orders
GROUP BY order_status
ORDER BY orders DESC;

-- 2. Monthly order trends
SELECT DATE_TRUNC('month', order_purchase_timestamp)::date AS month, COUNT(*) AS orders
FROM orders
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY month
ORDER BY month;

-- 3. Top product categories by item sales, using item price as sales revenue
SELECT COALESCE(pc.product_category_name_english, p.product_category_name, 'unknown') AS category,
       COUNT(*) AS items_sold,
       SUM(oi.price) AS item_sales
FROM order_items oi
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN product_categories pc ON p.product_category_name = pc.product_category_name
GROUP BY category
HAVING SUM(oi.price) > 0
ORDER BY item_sales DESC
LIMIT 10;

-- 4. Top-selling products by item sales
SELECT oi.product_id, COUNT(*) AS items_sold, SUM(oi.price) AS item_sales
FROM order_items oi
GROUP BY oi.product_id
ORDER BY item_sales DESC
LIMIT 10;

-- 5. Revenue by customer state, using order-level payment totals to avoid double-counting payments
WITH order_totals AS (
    SELECT order_id, SUM(payment_value) AS payment_total
    FROM order_payments
    GROUP BY order_id
)
SELECT c.customer_state, SUM(ot.payment_total) AS payment_revenue
FROM order_totals ot
JOIN orders o ON ot.order_id = o.order_id
JOIN customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_state
ORDER BY payment_revenue DESC;

-- 6. Average order value from payment totals
WITH order_totals AS (
    SELECT order_id, SUM(payment_value) AS payment_total
    FROM order_payments
    GROUP BY order_id
)
SELECT AVG(payment_total) AS average_order_value
FROM order_totals;

-- 7. Average delivery time for delivered orders
SELECT AVG(delivery_days) AS average_delivery_days
FROM orders
WHERE order_status = 'delivered' AND delivery_days IS NOT NULL;

-- 8. Late-delivery percentage for eligible delivered orders
SELECT AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) * 100 AS late_delivery_percentage
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL;

-- 9. Payment-method distribution
SELECT payment_type, COUNT(*) AS payment_records, SUM(payment_value) AS payment_value
FROM order_payments
GROUP BY payment_type
ORDER BY payment_records DESC;

-- 10. Sellers ranked by item sales
SELECT s.seller_id, s.seller_state, COUNT(*) AS items_sold, SUM(oi.price) AS item_sales
FROM sellers s
JOIN order_items oi ON s.seller_id = oi.seller_id
GROUP BY s.seller_id, s.seller_state
ORDER BY item_sales DESC
LIMIT 10;
