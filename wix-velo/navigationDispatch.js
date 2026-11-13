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
    const token = await getSecretValue(SECRET_NAME);
    if (typeof token !== "string" || !token) {
      throw new Error("Missing GITHUB_NAVIGATION_TOKEN secret");
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
