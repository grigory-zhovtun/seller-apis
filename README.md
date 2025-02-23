# Agregators Info Updater

This repository contains Python scripts for automating interactions with online marketplaces.
These scripts facilitate downloading, updating, and processing stock and price data for products.

## Scripts Overview
Both scripts using original stock data from Timeworld website, this data using for update prices and remnants to products in the agregators below

### `market.py`
This script is responsible for interfacing with the **Yandex Market API** to manage product data.  
It includes functionality for:
- Retrieving a list of products from Yandex Market.
- Downloading and updating stock information.
- Processing and converting price data.

### `seller.py`
This script interacts with the **Ozon Seller API** to handle product data.  
It includes functionality for:
- Fetching product listings from Ozon.
- Managing stock levels.
- Processing and adjusting pricing data.

## Configuration
Both scripts use environment variables for authentication and API access.  
Make sure to configure them correctly using a `.env` file or system environment variables.

## Logging
Logging is configured in both scripts for debugging and monitoring purposes.  
Logs provide detailed insights into API interactions and data processing.

## Usage
Run the scripts using:

```bash
python market.py
```
or
```bash
python seller.py
```

Ensure you have valid API credentials before executing the scripts.
