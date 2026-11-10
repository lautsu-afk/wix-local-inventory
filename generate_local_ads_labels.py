"""Create a Merchant Center supplemental feed using Wix CMS profile selections.

Does not change the existing local-inventory feed or the main Wix product feed.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import requests

ROOT = Path("docs")
INVENTORY_FEED = ROOT / "local_inventory.tsv"
LABELS_FEED = ROOT / "local_ads_labels.tsv"
CMS_URL = "https://www.wixapis.com/wix-data/v2/items/query"

HEADERS = {
    "Authorization": os.environ["WIX_API_KEY"],
    "wix-site-id": os.environ["WIX_SITE_ID"],
    "Content-Type": "application/json",
}


def read_collection(collection_id: str) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = requests.post(
            CMS_URL,
            json={
                "dataCollectionId": collection_id,
                "query": {"paging": {"limit": 100, "offset": offset}},
            },
            headers=HEADERS,
            timeout=60,
        )
        if response.status_code == 403:
            try:
                error_data = response.json()
                wix_error = str(error_data.get("message") or error_data.get("details") or "")
            except ValueError:
                wix_error = response.text[:500]
            raise RuntimeError(
                f"Wix CMS access denied for {collection_id} (HTTP 403). "
                "The GitHub WIX_API_KEY likely lacks Wix CMS 'Read Data Items' "
                "permission (SCOPE.DC-DATA.READ), or this collection's read "
                f"permissions deny access. Wix response: {wix_error[:500]}"
            )
        response.raise_for_status()
        page = response.json().get("dataItems", [])
        all_items.extend(item.get("data", {}) for item in page)
        if len(page) < 100:
            return all_items
        offset += 100


def build_labels() -> None:
    selections = read_collection("GoogleAdsLocalProfiles")
    if not selections:
        raise RuntimeError("No selection profiles in GoogleAdsLocalProfiles; refusing empty output")

    known_keys = set()
    chosen_keys = set()
    for item in selections:
        key = item.get("profileKey")
        if not key or key in known_keys:
            raise RuntimeError(f"Missing or duplicate profileKey: {key!r}")
        known_keys.add(key)
        if item.get("includeInLocalAds") is True:
            chosen_keys.add(key)

    products = read_collection("ProductShippingProfiles")
    if not products:
        raise RuntimeError("No product mapping in ProductShippingProfiles")

    by_product: dict[str, str] = {}
    for item in products:
        product_id = item.get("title")
        profile_key = item.get("profileKey")
        if not product_id or not profile_key or item.get("active") is False:
            continue
        if product_id in by_product and by_product[product_id] != profile_key:
            raise RuntimeError(f"Conflicting shipping profiles for product {product_id}")
        by_product[product_id] = profile_key

    with INVENTORY_FEED.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if not reader.fieldnames or "id" not in reader.fieldnames:
            raise RuntimeError("Existing inventory feed has no 'id' column")
        ids = [row["id"] for row in reader if row.get("id")]

    if not ids or len(ids) != len(set(ids)):
        raise RuntimeError("Local-inventory feed is empty or has duplicate item IDs")

    unknown = set(by_product.values()) - known_keys
    if unknown:
        # New profile keys are excluded until the merchant adds and enables
        # them in GoogleAdsLocalProfiles. Inventory exports must keep running.
        print(f"INFO: Unselected new product profile keys: {sorted(unknown)}")

    # Wix variant item IDs are product UUID + "_0", "_1", ...
    # The base UUID is also used as ProductShippingProfiles.title.
    output_rows = []
    selected_count = 0
    for item_id in ids:
        product_id = item_id.split("_", 1)[0]
        selected = by_product.get(product_id) in chosen_keys
        output_rows.append([item_id, "paikallinen" if selected else "muu"])
        selected_count += int(selected)

    LABELS_FEED.parent.mkdir(parents=True, exist_ok=True)
    temp_path = LABELS_FEED.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["id", "custom_label_0"])
        writer.writerows(output_rows)
    temp_path.replace(LABELS_FEED)
    print(
        f"Local Shopping feed updated: {len(output_rows)} items, "
        f"{selected_count} local, chosen profiles: {sorted(chosen_keys)}"
    )


if __name__ == "__main__":
    build_labels()
