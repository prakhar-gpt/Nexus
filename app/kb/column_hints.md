# Column hints

Fallback proposals when RapidFuzz scores a header below 70. These proposals require confirmation before rows enter `sales_clean`.

| Source header | Canonical |
| --- | --- |
| cust # | customer_id |
| item code | product_id |
| rev $ | revenue |
| sales | revenue |
| seg | segment |
| geo | region |
| prod cat | category |
| subcat | sub_category |
| qty | quantity |
| discount | discount_pct |
