from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import requests


# GitHub Actions antaa nämä arvot ohjelmalle salaisuuksista.
WIX_API_KEY = os.environ["WIX_API_KEY"]
WIX_SITE_ID = os.environ["WIX_SITE_ID"]
STORE_CODE = os.environ["STORE_CODE"]

# Sama Wix-tuoterajapinta, jota käytettiin Make.comissa.
PRODUCTS_URL = "https://www.wixapis.com/stores-reader/v1/products/query"

# GitHub Pages julkaisee docs-kansion sisällön.
OUTPUT_FILE = Path("docs/local_inventory.tsv")

HEADERS = {
    "Authorization": WIX_API_KEY,
    "wix-site-id": WIX_SITE_ID,
    "Content-Type": "application/json",
}


def wix_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    """Send a POST request to Wix and return the parsed JSON response."""
    response = requests.post(
        url,
        headers=HEADERS,
        json=body,
        timeout=60,
    )

    if not response.ok:
        print(f"Wix API error {response.status_code}")
        print(response.text)
        response.raise_for_status()

    return response.json()


def normalize_availability(value: str | None) -> str:
    """
    Convert Wix inventory status into a Google-supported availability value.
    """
    status = (value or "").strip().upper()

    mapping = {
        "IN_STOCK": "in_stock",
        "PARTIALLY_OUT_OF_STOCK": "limited_availability",
        "LIMITED_AVAILABILITY": "limited_availability",
        "OUT_OF_STOCK": "out_of_stock",
    }

    if status in mapping:
        return mapping[status]

    # Tuntematon arvo merkitään varmuuden vuoksi loppuneeksi.
    print(
        f"Warning: unknown Wix inventory status {value!r}; "
        "using out_of_stock"
    )
    return "out_of_stock"


def get_quantity(product: dict[str, Any]) -> int | str:
    """Return the Wix stock quantity when available."""
    stock = product.get("stock") or {}

    possible_values = [
        stock.get("quantity"),
        stock.get("quantityInStock"),
        stock.get("quantity_in_stock"),
        product.get("quantity"),
    ]

    for value in possible_values:
        if value is None:
            continue

        try:
            return int(float(value))
        except (TypeError, ValueError):
            print(f"Warning: unusual quantity value {value!r}")
            return value

    # Tyhjä quantity on sallittu silloin, kun Wix ei palauta tarkkaa saldoa.
    return ""


def get_inventory_status(product: dict[str, Any]) -> str | None:
    """Read inventory status from the Wix product response."""
    stock = product.get("stock") or {}

    return (
        stock.get("inventoryStatus")
        or stock.get("inventory_status")
        or product.get("inventoryStatus")
        or product.get("inventory_status")
    )


def get_product_id(product: dict[str, Any]) -> str | None:
    """Read the product ID that matches the Merchant Center item ID."""
    return product.get("id") or product.get("_id")


def product_is_visible(product: dict[str, Any]) -> bool:
    """Exclude a product only when Wix explicitly marks it as hidden."""
    return product.get("visible") is not False


def get_all_products() -> list[dict[str, Any]]:
    """
    Retrieve all Wix products.

    Wix returns up to 100 products per request, so requests are repeated
    with increasing offsets until the final partial page is reached.
    """
    products: list[dict[str, Any]] = []

    limit = 100
    offset = 0

    while True:
        request_body = {
            "query": {
                "paging": {
                    "limit": limit,
                    "offset": offset,
                }
            }
        }

        response_data = wix_post(PRODUCTS_URL, request_body)
        page = response_data.get("products", [])

        if not isinstance(page, list):
            raise RuntimeError(
                "Wix response did not contain a valid products array."
            )

        print(f"Products received at offset {offset}: {len(page)}")
        products.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return products


def create_pages_support_files() -> None:
    """Create small supporting files for GitHub Pages."""
    docs_directory = OUTPUT_FILE.parent
    docs_directory.mkdir(parents=True, exist_ok=True)

    # Prevent GitHub Pages from applying unnecessary Jekyll processing.
    (docs_directory / ".nojekyll").write_text("", encoding="utf-8")

    # GitHub Pages toimii luotettavasti, kun kansiossa on myös index.html.
    index_file = docs_directory / "index.html"

    index_file.write_text(
        """<!doctype html>
<html lang="fi">
<head>
  <meta charset="utf-8">
  <title>Local inventory feed</title>
</head>
<body>
  <p>
    <a href="local_inventory.tsv">Local inventory feed</a>
  </p>
</body>
</html>
""",
        encoding="utf-8",
    )


def build_inventory_file() -> None:
    """Fetch Wix products and write the Google local inventory TSV file."""
    products = get_all_products()
    create_pages_support_files()

    written_rows = 0
    skipped_hidden = 0
    skipped_without_id = 0

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(
            file,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            [
                "id",
                "store_code",
                "availability",
                "quantity",
            ]
        )

        for product in products:
            if not product_is_visible(product):
                skipped_hidden += 1
                continue

            product_id = get_product_id(product)

            if not product_id:
                print("Warning: product without ID skipped")
                skipped_without_id += 1
                continue

            inventory_status = get_inventory_status(product)
            availability = normalize_availability(inventory_status)
            quantity = get_quantity(product)

            writer.writerow(
                [
                    product_id,
                    STORE_CODE,
                    availability,
                    quantity,
                ]
            )

            written_rows += 1

    print("")
    print("Inventory generation completed.")
    print(f"Products received: {len(products)}")
    print(f"Rows written: {written_rows}")
    print(f"Hidden products skipped: {skipped_hidden}")
    print(f"Products without ID skipped: {skipped_without_id}")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_inventory_file()
