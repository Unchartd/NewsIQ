import type { Metadata } from "next";

import { PolicyView, StorageTable } from "@/components/legal/policy-view";
import { buildPageMetadata } from "@/lib/metadata";

import { normalizedPolicies, storageInventory } from "../normalized-content";

export const metadata: Metadata = buildPageMetadata(
  "Cookie Policy",
  "Every cookie and browser-storage item NewsIQ uses, which need your consent, and how to change your choices.",
  "/cookies"
);

export default function CookiesPage() {
  return (
    <PolicyView doc={normalizedPolicies.cookies} current="/cookies">
      <StorageTable items={storageInventory} />
    </PolicyView>
  );
}
