import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Get list of products from Ozon store

    This function uses the Ozon API to fetch the complete list of products available in the store.

    Args:
        last_id (int): last id of goods
        client_id (int): client id of goods
        seller_token (str): seller token

    Returns:
        list: list of goods
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Get articles of products from Ozon

    This function uses the list of products from Ozon store and
    then extracts and returns the `offer_id` from each product.

    Args:
        client_id (str): The Ozon Client ID
        seller_token (str): The Ozon seller token

    Returns:
        list of str: A list containing the offer IDs for all products.
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """Update price of products in Ozon store

    This function uses the list of products from Ozon store and updates the
    price of each product in the list.

    Args:
        prices (list): list of prices of products
        client_id (str): The Ozon Client ID
        seller_token (str): The Ozon seller token

    Returns:
        json: response from Ozon API

    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Update stocks of products in Ozon store

    This function uses the list of products from Ozon store and updates the
    stock of each product in the list.

    Args:
        stocks (list): list of stocks of products
        client_id (str): The Ozon Client ID
        seller_token (str): The Ozon seller token

    Returns:
        json: response from Ozon API
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Download and process stock data from Timeworld.

    This function downloads a ZIP archive containing an Excel file with stock data
    from the Timeworld website. It extracts the archive, reads the data into a Pandas
    DataFrame, converts it to a list of dictionaries, and returns the result.

    Returns:
        list[dict]: A list of dictionaries containing stock information.
    """
    # Скачать остатки с сайта
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    # Создаем список остатков часов:
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")  # Удалить файл
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """Generate actual stock levels from watch remnants.

    This function processes stock data from the Timeworld website and updates stock levels
    based on predefined rules:
    - If the stock is ">10", it is set to 100.
    - If the stock is "1", it is set to 0.
    - Otherwise, the stock remains unchanged.

    Additionally, if a watch's ID is not present in `offer_ids` (IDs from the Ozon store),
    its stock is set to 0.

    Args:
        watch_remnants (list[dict]): A list of dictionaries containing watch stock data.
        offer_ids (set[str]): A set of offer IDs from the Ozon store.

    Returns:
        list[dict]: A list of dictionaries with updated stock levels.
    """
    # Уберем то, что не загружено в seller
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Create new prices for actual stock levels.

    This function create new prices for actual products. New prices get from the
    Timeworld website for actual watch remnants.

    Args:
        watch_remnants (list[dict]): A list of dictionaries containing watch stock data.
        offer_ids (set[str]): A set of offer IDs from the Ozon store.

    Returns:
        list[dict]: A list of dictionaries with new prices.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """Converts the given price string to a digits-only string.

    Example (correct usage):
        >>> price_conversion("5'990.00 руб.")
        '5990'

    Example (incorrect usage):
        >>> price_conversion("invalid string")
        ''  # returns an empty string if no digits are found

    Args:
        price (str): The original price string.

    Returns:
        str: The price string containing only digits.
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделить список lst на части по n элементов"""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Send updated prices to the Ozon API.

    This function processes new prices and sends them to the Ozon API in batches of 1000 prices per request.

    Args:
        watch_remnants (list[dict]): A list of dictionaries containing watch stock data.
        client_id (str): The Ozon Client ID used for authentication.
        seller_token (str): The Ozon seller token used for API access.

    Returns:
        list[dict]: A list of dictionaries containing the updated prices.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Send updated stock levels to the Ozon API.

    This function processes stock updates and sends them to the Ozon API in batches of 100 items per request.
    It returns both the complete list of stock updates and a filtered list containing only items with stock greater than zero.

    Args:
        watch_remnants (list[dict]): A list of dictionaries containing watch stock data.
        client_id (str): The Ozon Client ID used for authentication.
        seller_token (str): The Ozon seller token used for API access.

    Returns:
        tuple:
            list[dict]: A list of dictionaries containing updated stock levels, excluding items with zero stock.
            list[dict]: A list of dictionaries containing all updated stock levels.
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
