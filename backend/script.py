import shopify
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TOKEN")
merchant = os.getenv("MERCHANT")
api_version = "2023-01"

if not token or not merchant:
    raise ValueError("TOKEN and MERCHANT environment variables must be set")

merchant_url = "posterwaofficial.myshopify.com"
api_session = shopify.Session(merchant_url, api_version, token)
shopify.ShopifyResource.activate_session(api_session)


def get_data(object_name):
    all_data = []
    attribute = getattr(shopify, object_name)
    try:
        data = attribute.find(since_id=0, limit=250)
    except Exception as e:
        print(f"Error fetching data for {object_name}: {e}")
        return all_data

    for d in data:
        all_data.append(d)
    while data.has_next_page():
        data = data.next_page()
        for d in data:
            all_data.append(d)
    return all_data
