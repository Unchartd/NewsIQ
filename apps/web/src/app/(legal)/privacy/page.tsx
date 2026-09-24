import type { Metadata } from "next";

import { PolicyView } from "@/components/legal/policy-view";
import { buildPageMetadata } from "@/lib/metadata";

import { normalizedPolicies } from "../normalized-content";

export const metadata: Metadata = buildPageMetadata(
  "Privacy Policy",
  "What personal data NewsIQ collects, why, who processes it, and your rights under India's DPDP Act and the GDPR.",
  "/privacy"
);

export default function PrivacyPage() {
  return <PolicyView doc={normalizedPolicies.privacy} current="/privacy" />;
}
