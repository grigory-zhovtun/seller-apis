"""Module for interfacing with the Yandex Market API and managing product data.

This module provides functions to download, update, and process stock and price
data for products from Yandex Market and Timeworld.
"""
import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """Get list of products from Yandex market.

    This function uses the Yandex market API to fetch the complete
    list of products available in the store.

    Args:
        page (str): Page number
        campaign_id (str): Campaign ID
        access_token (str): Access token

    Returns:
        list: List of products
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """Update stocks of products in Yandex market.

    This function uses the list of products from Yandex market and updates the
    stock of each product in the list.

    Args:
        stocks (list): list of stocks of products
        campaign_id (str): Campaign ID
        access_token (str): Access token

    Returns:
        json: response from Yandex API
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """Update price of products in Yandex market.

    This function uses the list of products from Yandex market and updates the
    price of each product in the list.

    Args:
        prices (list): list of prices of products
        campaign_id (str): Campaign ID
        access_token (str): Access token

    Returns:
        json: response from Yandex API

    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """Get articles of products from Yandex market.

    This function uses the list of products from Yandex market and
    then extracts and returns the `offer_id` from each product.

    Args:
        campaign_id (str): Campaign ID
        market_token (str): Access token

    Returns:
        list of str: A list containing the offer IDs for all products.
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Generate actual stock levels from watch remnants.

    This function processes stock data from the Timeworld website
    and updates stock levels based on predefined rules:

    - If the stock is ">10", it is set to 100.
    - If the stock is "1", it is set to 0.
    - Otherwise, the stock remains unchanged.

    Additionally, if a watch's ID is not present in `offer_ids`
    (IDs from the Yandex Market), its stock is set to 0.

    The function returns a list of dictionaries formatted for
    inventory updates, including stock count, warehouse ID, and timestamp.

    Args:
        watch_remnants (list[dict]): A list of dict with watch stock data.
        offer_ids (set[str]): A set of offer IDs from the Yandex Market.
        warehouse_id (str): The warehouse ID where stocks are updated.

    Returns:
        list[dict]: A list of dictionaries containing updated stock levels.
    """
    # Уберем то, что не загружено в market
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Generate new prices for available stock.

    This function calculates new prices for available products
    based on stock data from the Timeworld website. It processes
    watch remnants and extracts price values for products present
    in `offer_ids`.

    Args:
        watch_remnants (list[dict]): A list of dict with watch stock data.
        offer_ids (set[str]): A set of offer IDs from the Yandex Market.

    Returns:
        list[dict]: A list of dict with updated price information.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                # "feed": {"id": 0},
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    # "discountBase": 0,
                    "currencyId": "RUR",
                    # "vat": 0,
                },
                # "marketSku": 0,
                # "shopSku": "string",
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """Send updated prices to the Yandex Market API.

    This function processes new prices and sends them to the Yandex Market API
    in batches of 500 prices per request.

    Args:
        watch_remnants (list[dict]): A list of dict with watch stock data.
        campaign_id (str): The campaign ID.
        market_token (str): The API token for authentication.

    Returns:
        list[dict]: A list of dict with the updated price information.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """Send updated stock levels to the Yandex Market API.

    This asynchronous function processes stock updates and sends them
    to the Yandex Market API in batches of 2000 items per request.
    It returns a tuple containing both the complete list of stock updates
    and a filtered list that includes only items
    with a stock count greater than zero.

    Args:
        watch_remnants (list[dict]): A list of dict with watch stock data.
        campaign_id (str): The campaign ID.
        market_token (str): The Yandex Market API token.
        warehouse_id (str): The warehouse ID where the stocks are managed.

    Returns:
        tuple:
            list[dict]: A list of dict with updated stock levels,
            excluding items with zero stock.
            list[dict]: A list of dict with all updated stock levels.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    """Main function.

    This function includes the process of downloading the latest inventory
    and product prices from the Timeworld website and uploading them
    to the Yandex Market.

    """
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        # Обновить остатки FBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        # Поменять цены FBS
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        # Обновить остатки DBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        # Поменять цены DBS
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
