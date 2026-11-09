from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import requests


WIX_API_KEY = os.environ["WIX_API_KEY"]
WIX_SITE_ID = os.environ["WIX_SITE_ID"]
STORE_CODE = os.environ["STORE_CODE"]

PRODUCTS_URL = "https://www.wixapis.com/stores-reader/v1/products/query"
INVENTORY_URL = "https://www.wixapis.com/stores-reader/v2/inventoryItems/query"

OUTPUT_FILE = Path("docs/local_inventory.tsv")

HEADERS = {
    "Authorization": WIX_API_KEY,
    "wix-site-id": WIX_SITE_ID,
    "Content-Type": "application/json",
}


def wix_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
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


def get_all_products() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []

    limit = 100
    offset = 0

    while True:
        body = {
            "query": {
                "paging": {
                    "limit": limit,
                    "offset": offset,
                }
            }
        }

        data = wix_post(PRODUCTS_URL, body)
        page = data.get("products", [])

        print(f"Products received at offset {offset}: {len(page)}")
        products.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return products


def get_all_inventory_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    limit = 100
    offset = 0

    while True:
        body = {
            "query": {
                "paging": {
                    "limit": limit,
                    "offset": offset,
                }
            }
        }

        data = wix_post(INVENTORY_URL, body)
        page = data.get("inventoryItems", [])

        print(f"Inventory items at offset {offset}: {len(page)}")
        items.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return items


def get_product_variants(product_id: str) -> list[dict[str, Any]]:
    url = (
        "https://www.wixapis.com/stores-reader/v1/products/"
        f"{product_id}/variants/query"
    )

    variants: list[dict[str, Any]] = []

    limit = 100
    offset = 0

    while True:
        body = {
            "includeMerchantSpecificData": True,
            "paging": {
                "limit": limit,
                "offset": offset,
            },
        }

        data = wix_post(url, body)
        page = data.get("variants", [])

        variants.extend(page)

        if len(page) < limit:
            break

        offset += limit

    return variants


def create_inventory_lookup(
    inventory_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for item in inventory_items:
        product_id = item.get("productId")

        if not product_id:
            continue

        variant_lookup: dict[str, dict[str, Any]] = {}

        for variant in item.get("variants", []):
            variant_id = variant.get("variantId")

            if not variant_id:
                continue

            variant_lookup[variant_id] = {
                "inStock": variant.get("inStock"),
                "quantity": variant.get("quantity"),
                "availableForPreorder": variant.get(
                    "availableForPreorder"
                ),
            }

        lookup[product_id] = {
            "trackQuantity": item.get("trackQuantity", False),
            "variants": variant_lookup,
        }

    return lookup


def get_availability(
    inventory_data: dict[str, Any] | None,
    track_quantity: bool,
) -> str:
    """
    Convert Wix inventory into Google local inventory availability.

    When quantity is tracked:
      0     -> out_of_stock
      1-2   -> limited_availability
      3+    -> in_stock

    When quantity is not tracked:
      Wix inStock=True -> in_stock
      otherwise        -> out_of_stock
    """
    if not inventory_data:
        return "out_of_stock"

    if track_quantity:
        quantity = inventory_data.get("quantity")

        if quantity is not None:
            try:
                quantity = int(quantity)

                if quantity <= 0:
                    return "out_of_stock"

                if quantity <= 2:
                    return "limited_availability"

                return "in_stock"

            except (TypeError, ValueError):
                pass

    if inventory_data.get("inStock") is True:
        return "in_stock"

    return "out_of_stock"


def get_quantity(
    inventory_data: dict[str, Any] | None,
    track_quantity: bool,
) -> int | str:
    if not inventory_data:
        return 0

    if not track_quantity:
        return ""

    quantity = inventory_data.get("quantity")

    if quantity is None:
        return ""

    try:
        return int(quantity)
    except (TypeError, ValueError):
        return ""


def product_is_visible(product: dict[str, Any]) -> bool:
    return product.get("visible") is not False


def create_pages_support_files() -> None:
    docs_directory = OUTPUT_FILE.parent
    docs_directory.mkdir(parents=True, exist_ok=True)

    (docs_directory / ".nojekyll").write_text(
        "",
        encoding="utf-8",
    )

    (docs_directory / "index.html").write_text(
        """<!doctype html>
<html lang="fi">
<head>
  <meta charset="utf-8">
  <title>Local inventory feed</title>
</head>
<body>
  <p>
    <a href="local_inventory.tsv">
      Local inventory feed
    </a>
  </p>
</body>
</html>
""",
        encoding="utf-8",
    )


def build_inventory_file() -> None:
    print("Fetching Wix products...")
    products = get_all_products()

    print("")
    print("Fetching Wix inventory...")
    inventory_items = get_all_inventory_items()

    inventory_lookup = create_inventory_lookup(
        inventory_items
    )

    create_pages_support_files()

    rows: list[list[Any]] = []

    normal_products = 0
    variant_products = 0
    variant_rows = 0
    hidden_products = 0

    for product in products:
        if not product_is_visible(product):
            hidden_products += 1
            continue

        product_id = (
            product.get("id")
            or product.get("_id")
        )

        if not product_id:
            print("WARNING: product without ID skipped")
            continue

        variants = get_product_variants(
            product_id
        )

        visible_variants = [
            variant
            for variant in variants
            if (
                variant.get("variant") or {}
            ).get("visible") is not False
        ]

        product_inventory = inventory_lookup.get(
            product_id,
            {},
        )

        track_quantity = product_inventory.get(
            "trackQuantity",
            False,
        )

        inventory_variants = product_inventory.get(
            "variants",
            {},
        )

        #
        # VARIANT PRODUCT
        #
        # Wix Google feed uses:
        #
        # product-id_0
        # product-id_1
        # product-id_2
        #
        # in the same order that Wix Query Product Variants
        # returns the visible variants.
        #
        if len(visible_variants) > 1:
            variant_products += 1

            print("")
            print(
                f"Variant product {product_id}: "
                f"{len(visible_variants)} variants"
            )

            for index, variant in enumerate(
                visible_variants
            ):
                variant_id = variant.get("id")

                if not variant_id:
                    print(
                        f"WARNING: variant {index} "
                        "has no ID"
                    )
                    continue

                google_id = (
                    f"{product_id}_{index}"
                )

                inventory_data = (
                    inventory_variants.get(
                        variant_id
                    )
                )

                availability = get_availability(
                    inventory_data,
                    track_quantity,
                )

                quantity = get_quantity(
                    inventory_data,
                    track_quantity,
                )

                choices = variant.get(
                    "choices",
                    {},
                )

                print(
                    f"  {google_id}"
                    f" | Wix variant {variant_id}"
                    f" | {choices}"
                    f" | {availability}"
                    f" | qty {quantity}"
                )

                rows.append(
                    [
                        google_id,
                        STORE_CODE,
                        availability,
                        quantity,
                    ]
                )

                variant_rows += 1

        #
        # NORMAL PRODUCT
        #
        else:
            normal_products += 1

            inventory_data = None

            #
            # A normal Wix product normally still has
            # one underlying inventory variant.
            #
            if visible_variants:
                wix_variant_id = (
                    visible_variants[0].get("id")
                )

                inventory_data = (
                    inventory_variants.get(
                        wix_variant_id
                    )
                )

            #
            # Fallback for unusual inventory structures.
            #
            if (
                inventory_data is None
                and inventory_variants
            ):
                inventory_data = next(
                    iter(
                        inventory_variants.values()
                    )
                )

            availability = get_availability(
                inventory_data,
                track_quantity,
            )

            quantity = get_quantity(
                inventory_data,
                track_quantity,
            )

            rows.append(
                [
                    product_id,
                    STORE_CODE,
                    availability,
                    quantity,
                ]
            )

    #
    # Safety check:
    # Merchant Center IDs must be unique.
    #
    ids = [
        row[0]
        for row in rows
    ]

    seen: set[str] = set()
    duplicate_ids: set[str] = set()

    for item_id in ids:
        if item_id in seen:
            duplicate_ids.add(item_id)

        seen.add(item_id)

    if duplicate_ids:
        raise RuntimeError(
            "Duplicate Google product IDs generated: "
            + ", ".join(
                sorted(duplicate_ids)
            )
        )

    #
    # Write TSV feed.
    #
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

        writer.writerows(rows)

    print("")
    print("======================================")
    print("Local inventory feed completed")
    print("======================================")
    print(
        f"Wix products received: "
        f"{len(products)}"
    )
    print(
        f"Normal product rows: "
        f"{normal_products}"
    )
    print(
        f"Variant products: "
        f"{variant_products}"
    )
    print(
        f"Variant rows: "
        f"{variant_rows}"
    )
    print(
        f"Hidden products skipped: "
        f"{hidden_products}"
    )
    print(
        f"TOTAL GOOGLE ROWS: "
        f"{len(rows)}"
    )
    print(
        f"Output: "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":
    build_inventory_file()
