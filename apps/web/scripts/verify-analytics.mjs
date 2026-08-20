/**
 * Post-build gate for the analytics delivery layer.
 *
 * Runs as `postbuild`, so it executes inside the Docker image build too — a
 * regression here fails the image rather than shipping silently.
 *
 * Two defects it exists to prevent, both found live in production:
 *
 *  1. gtag.js was loaded but `gtag('config', …)` was never called on page
 *     load. It only ran from the GA4 provider's identify(), i.e. after a
 *     login, so anonymous traffic — effectively the whole audience of a
 *     public news site — was never measured. The page looked instrumented.
 *
 *  2. A hardcoded `|| "G-NEWSIQ"` fallback meant a missing measurement id
 *     produced a plausible-looking id in logs while discarding every hit.
 *
 * The checks are conditional on the id being supplied, so local builds
 * without analytics keys stay green.
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const APP_DIR = join(process.cwd(), ".next", "server", "app");
const GA_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID?.trim();

/**
 * Matches the gtag.js loader specifically, anchored on the full origin and
 * path. A bare `includes("googletagmanager.com")` would both over-match (any
 * string mentioning the host anywhere) and under-specify what we care about,
 * which is that the loader script itself is present.
 */
const GTAG_SCRIPT_SRC = /https:\/\/www\.googletagmanager\.com\/gtag\/js\?id=/;

/** Collect prerendered HTML, which is where the bootstrap script lands. */
async function htmlFiles(dir) {
  const found = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return found;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) found.push(...(await htmlFiles(full)));
    else if (entry.name.endsWith(".html")) found.push(full);
  }
  return found;
}

const files = await htmlFiles(APP_DIR);
if (files.length === 0) {
  console.log("[verify-analytics] no prerendered HTML found; skipping.");
  process.exit(0);
}

const contents = await Promise.all(files.map((f) => readFile(f, "utf8")));
const joined = contents.join("\n");

const failures = [];

if (GA_ID) {
  if (!joined.includes("gtag('config'")) {
    failures.push(
      `NEXT_PUBLIC_GA_MEASUREMENT_ID is set (${GA_ID}) but no gtag('config', …) ` +
        "call was emitted. gtag.js would load bound to no measurement, and every " +
        "event would queue in dataLayer and never send."
    );
  }
  if (!joined.includes(GA_ID)) {
    failures.push(`the build does not contain the measurement id ${GA_ID}.`);
  }
  if (!joined.includes("send_page_view: false")) {
    failures.push(
      "gtag config is missing send_page_view:false; analytics-tracker.tsx already " +
        "sends pageviews on route change, so SPA navigations would double-count."
    );
  }
} else if (GTAG_SCRIPT_SRC.test(joined)) {
  failures.push(
    "no measurement id was supplied, yet gtag.js is still loaded. A missing id " +
      "must disable GA4 outright rather than fall back to a placeholder."
  );
}

// A placeholder must never reach a built artifact, however it got there.
for (const bad of ["G-NEWSIQ", "phc_mock_token_newsiq"]) {
  if (joined.includes(bad)) {
    failures.push(`placeholder analytics key "${bad}" is present in the build output.`);
  }
}

if (failures.length > 0) {
  console.error("[verify-analytics] FAILED:");
  for (const f of failures) console.error(`  - ${f}`);
  process.exit(1);
}

console.log(
  GA_ID
    ? `[verify-analytics] OK — GA4 configured (${GA_ID}), pageviews client-driven.`
    : "[verify-analytics] OK — no measurement id supplied; GA4 correctly absent."
);
