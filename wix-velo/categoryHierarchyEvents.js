// Wix Velo backend/categoryHierarchyEvents.js
// Copy this file to the Wix site's backend folder. A separate helper avoids
// changing any of the site's existing product, inventory or shipping logic.
//
// The corresponding exported wixStores_onCollectionCreated/Deleted handlers
// must be added to the site's existing backend/events.js.
// See wix-velo/CATEGORY_EVENTS_INSTALL.md.

import wixData from "wix-data";

const HIERARCHY = "Kategoriahierarkia";
const STORES = "Stores/Collections";
const READ_OPTIONS = { suppressAuth: true, consistentRead: true };
const WRITE_OPTIONS = { suppressAuth: true };

function readableId(value) {
  return (typeof value === "string" && value.trim()) || null;
}

async function fetchStoreCategory(id) {
  try {
    return await wixData.get(STORES, id, READ_OPTIONS);
  } catch (error) {
    // The store's CMS collection may not immediately reflect the event.
    // A separate scheduled reconciliation continues to run every 5 minutes.
    console.warn("Kategoriahierarkia: kaupan kategorian luku epäonnistui", id, error);
    return null;
  }
}

async function fetchHierarchyItem(id) {
  return wixData.get(HIERARCHY, id, READ_OPTIONS);
}

export async function onCategoryCreated(event = {}) {
  const id = readableId(event._id || event.collectionId);
  if (!id) {
    console.warn("Kategoriahierarkia: luontitapahtumasta puuttuu kategorian tunniste");
    return;
  }
  try {
    const existing = await fetchHierarchyItem(id);
    if (existing) return; // Idempotent: never reset an already chosen parent.

    const storeCategory = await fetchStoreCategory(id);
    const name = storeCategory?.name || event.name;
    if (!name) {
      console.warn("Kategoriahierarkia: kategoriasta ei saatu nimeä", id);
      return;
    }

    await wixData.insert(
      HIERARCHY,
      {
        _id: id,
        title: name,
        wixCategoryId: id,
        wixSlug: storeCategory?.slug || event.slug || "",
        isMain: false,
        // parent intentionally empty: user chooses it in CMS.
      },
      WRITE_OPTIONS
    );
    console.info("Kategoriahierarkia: uusi kategoria lisätty", name, id);
  } catch (error) {
    // If the event is retried or GitHub reconciliation already inserted
    // the row, do not overwrite its parent.
    const existing = await fetchHierarchyItem(id).catch(() => null);
    if (!existing) console.error("Kategoriahierarkia: lisäys epäonnistui", id, error);
  }
}

export async function onCategoryUpdated(event = {}) {
  const id = readableId(event.collectionId || event._id);
  if (!id) return;

  // Wix V1 update event may contain only an ID and list of changed fields,
  // not the new category name. Read the Wix app collection before saving.
  const storeCategory = await fetchStoreCategory(id);
  if (!storeCategory?.name) return; // Five-minute reconciliation is fallback.

  const existing = await fetchHierarchyItem(id).catch(() => null);
  if (!existing) {
    await onCategoryCreated({ _id: id, name: storeCategory.name, slug: storeCategory.slug });
    return;
  }

  const next = { ...existing };
  let changed = false;
  if (existing.title !== storeCategory.name) {
    next.title = storeCategory.name;
    changed = true;
  }
  if (storeCategory.slug && existing.wixSlug !== storeCategory.slug) {
    next.wixSlug = storeCategory.slug;
    changed = true;
  }
  // Do not touch parent or isMain: these are edited by the store owner.
  if (changed) {
    await wixData.update(HIERARCHY, next, WRITE_OPTIONS);
    console.info("Kategoriahierarkia: kategorian tiedot päivitetty", id);
  }
}

export async function onCategoryDeleted(event = {}) {
  const id = readableId(event.collectionId || event._id);
  if (!id) return;
  try {
    const existing = await fetchHierarchyItem(id);
    if (!existing) return;
    await wixData.remove(HIERARCHY, id, WRITE_OPTIONS);
    console.info("Kategoriahierarkia: poistettu Storesista poistettu kategoria", id);
  } catch (error) {
    console.error("Kategoriahierarkia: poisto epäonnistui", id, error);
  }
}
