// Wix Velo: backend/navigationDispatch.js
// Only the backend may read the secret and call the GitHub API.
// Keep this separate from product, shipping and inventory logic.
import { fetch } from "wix-fetch";
import { secrets } from "wix-secrets-backend.v2";
import { elevate } from "wix-auth";

const getSecretValue = elevate(secrets.getSecretValue);
const DISPATCH_URL =
  "https://api.github.com/repos/lautsu-afk/wix-local-inventory/dispatches";
const SECRET_NAME = "GITHUB_NAVIGATION_TOKEN";

/**
 * Request a category navigation refresh, without touching the inventory job.
 * Called by Kategoriahierarkia CMS after-hooks. Never expose this as a
 * public webMethod: the GitHub token is a backend-only secret.
 *
 * A failed dispatch is logged rather than making a successfully saved CMS
 * change appear unsuccessful. No token or request headers are logged.
 */
export async function requestNavigationRefresh(reason = "cms-change") {
  try {
    // Wix APIs may return { value: "..." }; some Velo examples return a string.
    // Accept both without ever logging the secret or its value.
    const secretResponse = await getSecretValue(SECRET_NAME);
    const token =
      typeof secretResponse === "string"
        ? secretResponse.trim()
        : typeof secretResponse?.value === "string"
          ? secretResponse.value.trim()
          : "";
    if (!token) {
      throw new Error("GITHUB_NAVIGATION_TOKEN could not be read or is empty");
    }
    const response = await fetch(DISPATCH_URL, {
      method: "post",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: "wix-category-navigation",
        client_payload: {
          source: "wix-velo",
          reason: String(reason).slice(0, 80),
        },
      }),
    });
    if (response.status !== 204) {
      throw new Error(`GitHub repository_dispatch returned HTTP ${response.status}`);
    }
    console.info("Kategoriahierarkia: GitHub navigation refresh requested", reason);
    return true;
  } catch (error) {
    console.error("Kategoriahierarkia: GitHub dispatch failed", reason, error);
    return false;
  }
}
