# Store raw data folder

Each store has its own folder to keep the crawler output isolated and easy to review.

## Expected structure

- amazon/
  - amazon_full_catalog.json
  - amazon_sample_5_per_category.json
- danube/
  - danube_full_catalog.json
  - danube_sample_5_per_category.json
- tamimi/
  - tamimi_full_catalog.json
  - tamimi_sample_5_per_category.json

## Standards

- Keep raw crawler output in the full catalog file.
- Keep a small QA sample per category in the sample file.
- Use consistent field names across all stores.
- Avoid mixing raw and processed files in the same folder.
