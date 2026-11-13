#!/usr/bin/env python3
# Category membership navigation publication after Wix product reassignment, 2026-11-13.
# Product-category cleanup and fourth-level membership publication (2026-11-13).
"""Build a read-only navigation manifest for lautamaki.fi from Wix Catalog V1.

Source of truth:
- category names, slugs and visibility: Wix Stores Catalog V1
- product collection membership: Wix Stores Catalog V1
- parent-category hierarchy: editable Wix CMS Kategoriahierarkia references
- presentation text overrides: navigation_config.json (fixed labels, headings)
Only the navigation CMS index of category names and new categories is maintained; store products and category memberships are not modified. Output serves the existing custom embeds.
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
CMS_QUERY_URL = "https://www.wixapis.com/wix-data/v2/items/query"
CMS_INSERT_URL = "https://www.wixapis.com/wix-data/v2/bulk/items/insert"
CMS_PATCH_URL = "https://www.wixapis.com/wix-data/v2/items/"
CMS_COLLECTION_ID = "Kategoriahierarkia"
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


def query_cms_hierarchy() -> list[dict]:
    """Read the authoritative hierarchy from editable Wix CMS.
    Fail closed if CMS cannot be read so an outdated config is never
    silently republished over the owner's CMS changes.
    """
    rows: list[dict] = []
    session = requests.Session()
    for offset in range(0, 10000, PAGE_LIMIT):
        response = session.post(
            CMS_QUERY_URL,
            headers=HEADERS,
            json={
                "dataCollectionId": CMS_COLLECTION_ID,
                "query": {"paging": {"limit": PAGE_LIMIT, "offset": offset}},
            },
            timeout=60,
        )
        if not response.ok:
            print(
                "Wix CMS hierarchy query failed", response.status_code,
                response.text[:1000], file=sys.stderr,
            )
            response.raise_for_status()
        batch = response.json().get("dataItems", [])
        rows.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    if not rows:
        raise RuntimeError("Kategoriahierarkia CMS collection is empty")
    return rows


def sync_cms_catalog(
    categories: list[dict],
    cms_items: list[dict],
    main_ids: list[str],
    parent_of: dict[str, str | None],
) -> None:
    """Keep the CMS editor's category selection up to date.

    Only the display label, Wix slug and missing category records are managed.
    Existing admin-selected parent references and isMain flags are NEVER
    overwritten. CMS permission errors are reported, without preventing the
    already-working breadcrumb manifest from being refreshed.
    """
    by_id = {item["id"]: item for item in cms_items}
    missing = [
        c for c in categories
        if c["name"] != ALL_PRODUCTS_NAME and c["id"] not in by_id
    ]
    session = requests.Session()
    if missing:
        records = [
            {
                "id": c["id"],
                "data": {
                    "title": c["name"],
                    "wixCategoryId": c["id"],
                    "wixSlug": c["slug"],
                    "isMain": c["id"] in main_ids,
                },
            }
            for c in missing
        ]
        try:
            resp = session.post(
                CMS_INSERT_URL,
                headers=HEADERS,
                json={
                    "dataCollectionId": CMS_COLLECTION_ID,
                    "dataItems": records,
                    "returnEntity": False,
                },
                timeout=60,
            )
            resp.raise_for_status()
            meta = resp.json().get("bulkActionMetadata", {})
            if meta.get("totalFailures", 0):
                raise RuntimeError(f"CMS insert failures: {meta}")
            print(f"Added {len(records)} newly created categories to CMS")
        except (requests.RequestException, RuntimeError) as err:
            print(f"WARNING: Unable to add new CMS categories: {err}", file=sys.stderr)

    for c in categories:
        item = by_id.get(c["id"])
        if not item:
            continue
        old = item.get("data", {})
        changes = []
        for field, value in (("title", c["name"]), ("wixSlug", c["slug"])):
            if old.get(field) != value:
                changes.append({
                    "fieldPath": field,
                    "action": "SET_FIELD",
                    "setFieldOptions": {"value": value},
                })
        if not changes:
            continue
        try:
            resp = session.patch(
                CMS_PATCH_URL + c["id"],
                headers=HEADERS,
                json={
                    "dataCollectionId": CMS_COLLECTION_ID,
                    "patch": {
                        "dataItemId": c["id"],
                        "fieldModifications": changes,
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            print("Refreshed CMS label/URL for", c["name"])
        except requests.RequestException as err:
            print(
                f"WARNING: Unable to update CMS category {c['name']}: {err}",
                file=sys.stderr,
            )

    # The new CMS rows should inherit an inferred parent when unambiguous,
    # so they become immediately editable with a named reference in Wix.
    missing_ids = {c["id"] for c in missing}
    for c in missing:
        parent = parent_of.get(c["id"])
        if not parent or parent in missing_ids:
            continue
        try:
            resp = session.patch(
                CMS_PATCH_URL + c["id"],
                headers=HEADERS,
                json={
                    "dataCollectionId": CMS_COLLECTION_ID,
                    "patch": {
                        "dataItemId": c["id"],
                        "fieldModifications": [{
                            "fieldPath": "parent",
                            "action": "SET_FIELD",
                            "setFieldOptions": {"value": parent},
                        }],
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
        except requests.RequestException as err:
            print(
                f"WARNING: Unable to assign CMS parent for {c['name']}: {err}",
                file=sys.stderr,
            )


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

    cms_items = query_cms_hierarchy()
    cms_by_id = {}
    for item in cms_items:
        item_data = item.get("data", {})
        cid = item_data.get("wixCategoryId") or item.get("id")
        if cid in cms_by_id:
            raise RuntimeError("Duplicate Wix category ID in Kategoriahierarkia: " + cid)
        if item_data.get("wixCategoryId") and item_data["wixCategoryId"] != item["id"]:
            raise RuntimeError("CMS category IDs do not match: " + cid)
        cms_by_id[cid] = item_data

    main_ids = [
        cid for cid, data in cms_by_id.items()
        if data.get("isMain") is True and cid in active
    ]
    if not main_ids:
        raise RuntimeError("No main categories configured in Kategoriahierarkia")

    overrides = config.get("main_display_name_overrides", {})
    parent_of: dict[str, str | None] = dict(config["parent_by_category_id"])
    # Existing CMS rows are authoritative even when parent is intentionally
    # cleared. Name/slug continue to come from the current Wix Stores catalog.
    for cid, data in cms_by_id.items():
        parent_of[cid] = data.get("parent") or None
    all_id = all_products["id"]
    parent_of[all_id] = None
    for cid in main_ids:
        parent_of[cid] = None

    # CMS is the authoritative hierarchy. Its parent references may point to
    # several nested levels and take precedence over legacy static mappings.
    # Raise an explicit error rather than publishing a stale/partial hierarchy
    # if a CMS parent points to a missing row.
    for cid, parent_id in parent_of.items():
        if cid in cms_by_id and parent_id and parent_id not in cms_by_id:
            raise RuntimeError(
                f"Kategoriahierarkia parent {parent_id} for {cid} is missing in Wix CMS"
            )

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
        if cid in (all_id, *main_ids) or cid in cms_by_id:
            continue
        # New categories without a CMS row are temporarily auto-inferred.
        # Explicit CMS choices always take precedence.
        likely = most_likely_main(cid)
        parent_of[cid] = likely
        if likely:
            inferred.append(cat["name"])

    sync_cms_catalog(categories, cms_items, main_ids, parent_of)

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
    # All Products is the navigation root: show only the five CMS main
    # categories as pills, without changing category hierarchy or breadcrumbs.
    root_children = sorted(
        (active[cid] for cid in main_ids),
        key=lambda c: get_label(c, overrides).casefold(),
    )
    menus[all_products["slug"]] = {
        "name": "Kaikki tuotteet",
        "description": "",
        "links": [
            {"label": get_label(c, overrides), "href": url(c["slug"])}
            for c in root_children
        ],
    }
    for mid, cat in active.items():
        if mid == all_id:
            continue
        kids = [c for cid, c in active.items() if parent_of.get(cid) == mid]
        # Any category with direct children gets an Alakategoriat navigation,
        # including nested groups below the five original main categories.
        kids.sort(key=lambda x: x["name"].casefold())
        if not kids:
            continue
        menus[cat["slug"]] = {
            "name": get_label(cat, overrides, breadcrumb=False),
            "description": desc_by_id.get(mid, ""),
            "links": [{"label": get_label(c, overrides), "href": url(c["slug"])} for c in kids],
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
            # New nested CMS categories inherit their closest named ancestor's
            # breadcrumb priority. Otherwise a specific child defaults to 65
            # and incorrectly loses to its parent (e.g. Ruuvimeisselit).
            score = priorities.get(name, main_priority.get(name))
            if score is None:
                ancestor = parent_of.get(cid)
                seen_ancestors = {cid}
                while ancestor in active and ancestor not in seen_ancestors:
                    seen_ancestors.add(ancestor)
                    ancestor_name = active[ancestor]["name"]
                    ancestor_score = priorities.get(
                        ancestor_name, main_priority.get(ancestor_name)
                    )
                    if ancestor_score is not None:
                        score = ancestor_score
                        break
                    ancestor = parent_of.get(ancestor)
            if score is None:
                score = 65
            # Prefer the most specific eligible group at each deeper level.
            # CMS parent references determine depth; no hardcoded level limit.
            if len(paths_by_id[cid]) > 3:
                score += 10 * (len(paths_by_id[cid]) - 3)
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
