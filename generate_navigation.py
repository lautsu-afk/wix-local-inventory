#!/usr/bin/env python3
"""Build a read-only navigation manifest for lautamaki.fi from Wix Catalog V1.

Source of truth:
- category names, slugs and visibility: Wix Stores Catalog V1
- product collection membership: Wix Stores Catalog V1
- parent-category hierarchy: navigation_config.json (stable Wix category IDs)
No Wix data is modified. Output is used by the site's existing custom embeds.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

WIX_API_KEY = os.environ["WIX_API_KEY"]
WIX_SITE_ID = os.environ["WIX_SITE_ID"]
BASE = "https://www.wixapis.com/stores-reader/v1"
CONFIG_FILE = Path("navigation_config.json")
OUTPUT_FILE = Path("docs/navigation.json")
SCRIPT_OUTPUT_FILE = Path("docs/navigation.js")
PAGE_LIMIT = 100

HEADERS = {
    "Authorization": WIX_API_KEY,
    "wix-site-id": WIX_SITE_ID,
    "Content-Type": "application/json",
}
ALL_PRODUCTS_NAME = "All Products"


def query_all(endpoint: str, field: str, *, include_hidden: bool = False) -> list[dict]:
    records: list[dict] = []
    session = requests.Session()
    for offset in range(0, 100000, PAGE_LIMIT):
        payload = {"query": {"paging": {"limit": PAGE_LIMIT, "offset": offset}}}
        if include_hidden:
            payload["includeHiddenProducts"] = True
        response = session.post(
            BASE + endpoint,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )
        if not response.ok:
            print("Wix API error", response.status_code, response.text[:1000], file=sys.stderr)
            response.raise_for_status()
        batch = response.json().get(field, [])
        records.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    else:
        raise RuntimeError("Wix API page limit exhausted")
    return records


def url(slug: str) -> str:
    return "/category/" + quote(slug, safe="")


def get_label(category: dict, overrides: dict, *, breadcrumb: bool = True) -> str:
    label = category["name"]
    override = overrides.get(category["id"])
    if override and label == override.get("whenWixName"):
        label = override.get("breadcrumb" if breadcrumb else "heading") or label
    return label


def main() -> None:
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    categories = query_all("/collections/query", "collections")
    products = query_all("/products/query", "products", include_hidden=True)
    by_id = {c["id"]: c for c in categories}
    active = {c["id"]: c for c in categories if c.get("visible") is not False}
    all_products = next((c for c in categories if c["name"] == ALL_PRODUCTS_NAME), None)
    if not all_products or all_products["id"] not in active:
        raise RuntimeError("Wix All Products category is missing")

    main_ids = config["main_category_ids"]
    if any(i not in active for i in main_ids):
        raise RuntimeError("At least one configured main category is missing or inactive")

    overrides = config.get("main_display_name_overrides", {})
    configured_parents = config["parent_by_category_id"]
    parent_of: dict[str, str | None] = dict(configured_parents)
    all_id = all_products["id"]
    parent_of[all_id] = None

    # Product membership gives a safe indication of moved/new subcategories.
    category_members: dict[str, set[str]] = defaultdict(set)
    for p in products:
        for cid in p.get("collectionIds", []):
            category_members[cid].add(p["id"])

    def most_likely_main(cid: str) -> str | None:
        category_product_ids = category_members[cid]
        if not category_product_ids:
            return None
        overlaps = Counter({
            mid: len(category_product_ids & category_members[mid])
            for mid in main_ids if mid != cid
        })
        if not overlaps:
            return None
        best = max(overlaps.values())
        # Avoid inventing a parent if main-category membership is ambiguous.
        winners = [k for k, v in overlaps.items() if v == best and v > 0]
        return winners[0] if len(winners) == 1 else None

    inferred = []
    # Existing parent mappings are explicit editorial choices. Product overlap
    # alone must not move an established subcategory into another main category.
    # Brand-new categories can be assigned when their membership has one clear
    # main-category winner. Ambiguous ones stay directly below All Products.
    for cid, cat in active.items():
        if cid in (all_id, *main_ids) or cid in parent_of:
            continue
        likely = most_likely_main(cid)
        parent_of[cid] = likely
        if likely:
            inferred.append(cat["name"])

    first = {"label": "Kaikki tuotteet", "href": url(all_products["slug"])}
    paths_by_id: dict[str, list[dict]] = {}

    def path_for(cid: str, seen: frozenset[str] = frozenset()) -> list[dict]:
        if cid == all_id:
            return [first]
        if cid not in active:
            return [first]
        if cid in paths_by_id:
            return paths_by_id[cid]
        if cid in seen:
            raise RuntimeError("Category hierarchy cycle detected: " + cid)
        category = active[cid]
        item = {"label": get_label(category, overrides), "href": url(category["slug"])}
        parent = parent_of.get(cid)
        if parent == cid or parent == all_id or parent not in active:
            parent = None
        base = path_for(parent, seen | {cid}) if parent else [first]
        result = base + [item]
        paths_by_id[cid] = result
        return result

    paths_by_id[all_id] = [first]
    for cid in active:
        path_for(cid)

    paths = {cat["slug"]: paths_by_id[cid] for cid, cat in active.items()}
    menus: dict[str, dict] = {}
    desc_by_id = config.get("menu_descriptions_by_main_id", {})
    for mid in main_ids:
        cat = active[mid]
        kids = [c for cid, c in active.items() if parent_of.get(cid) == mid]
        # Under Catalog V1, parent relations are virtual. Use current names/URLs.
        kids.sort(key=lambda x: x["name"].casefold())
        if not kids:
            continue
        menus[cat["slug"]] = {
            "name": get_label(cat, overrides, breadcrumb=False),
            "description": desc_by_id.get(mid, ""),
            "links": [{"label": c["name"], "href": url(c["slug"])} for c in kids],
        }

    # Product category selection follows the existing breadcrumb priorities,
    # while recalculating selection from CURRENT Wix product associations.
    priorities = {
        "Peitekilvet ja vääntönupit": 105, "Noki- ja tuhkaluukut": 105,
        "Savupellit": 101, "Jatkojohdot ja valaisimet": 106,
        "Työkalupakit ja säilytys": 102,
        "Ruuvauskärjet ja ruuvimeisselit": 106,
        "Mittausvälineet": 104, "Sähkötyökalut": 105,
        "Työkalusarjat": 100, "Kottikärryn ym. renkaat": 103,
        "Maantiesuolat": 107, "Sähköaitatarvikkeet": 106,
        "Eläintenhoito": 101, "Käärintämuovit": 105,
        "Lannoitteet": 105, "Kasvinsuojeluaineet": 105,
        "Villat, eristeet ja sulkupaperit": 101,
        "Rakennuslevyt": 95,
        "Tuuletusputket ja läpiviennit katolle": 100,
        "Sauna": 104, "Tulisijat ja tarvikkeet": 90,
        "Perustus": 99, "Kiinnitystarvikkeet": 100,
        "LVI": 90, "Maalaus, lakkaus ja pintakäsittely": 94,
        "Käsityökalut": 90, "Sähkötarvikkkeet": 80,
        "Helat ja lukot": 85, "Ajoneuvojen ja työkoneiden tarvikkeet": 95,
        "Kastelu ja pesu": 91, "Taloustavarat": 90,
        "Lämpömittarit": 95, "Liput ja liputustarvikkeet": 95,
        "Hitsauspuikot": 101, "Puutavara": 96,
        "Salaoja- ja sadevesiputket ja -osat": 98,
    }
    main_priority = {
        "Työkalut": 45,
        "Työvaatteet, jalkineet ja suojaimet": 40,
        "Maataloustarvikkeet": 35,
        "Koti, piha ja puutarha": 30,
        "Rakennustarvikkeet": 20,
    }
    product_categories: dict[str, str] = {}
    for p in products:
        candidates = []
        for cid in p.get("collectionIds", []):
            category = active.get(cid)
            if not category or cid == all_id:
                continue
            name = category["name"]
            score = priorities.get(name, main_priority.get(name, 65))
            # Prefer deeper specific categories on otherwise similar products.
            if len(paths_by_id[cid]) > 3:
                score += 10
            if name == "Sauna" and re.search(
                r"sauna|kiuas|harvia|saunapiippu", p.get("name", ""), re.I
            ):
                score += 6
            if name == "Käsityökalut" and re.search(
                r"ruuvimeisseli|ruuvauskärk", p.get("name", ""), re.I
            ):
                score = 81
            if name == "Työkalusarjat" and "sarja" in p.get("name", "").lower():
                score += 6
            candidates.append((score, name.casefold(), cid))
        best_cid = (
            sorted(candidates, key=lambda a: (-a[0], a[1]))[0][2]
            if candidates else all_id
        )
        product_categories[p["slug"].lower()] = active[best_cid]["slug"]

    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "paths": paths,
        "menus": menus,
        "productCategories": product_categories,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Avoid triggering a Pages rebuild when nothing in the catalog has changed.
    # Timestamp must only update when the content actually changes.
    if OUTPUT_FILE.exists():
        old = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        old.pop("generatedAt", None)
        new = dict(result)
        new.pop("generatedAt", None)
        if old == new and SCRIPT_OUTPUT_FILE.exists():
            print("No navigation changes to publish.")
            return
        if old == new:
            # Generate the JS variant without refreshing the data timestamp.
            result = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))

    raw = json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    OUTPUT_FILE.write_text(raw + "\n", encoding="utf-8")
    # The browser loads the JavaScript variant as a regular script.
    # This avoids CORS problems between Wix and GitHub Pages.
    SCRIPT_OUTPUT_FILE.write_text(
        "window.__lautamakiNavData=" + raw
        + ";window.dispatchEvent(new Event('lautamaki-navigation-updated'));\n",
        encoding="utf-8",
    )
    print(
        f"Navigation refreshed: {len(paths)} categories, {len(product_categories)} products, "
        f"{len(menus)} submenu groups; inferred={inferred}"
    )


if __name__ == "__main__":
    main()
