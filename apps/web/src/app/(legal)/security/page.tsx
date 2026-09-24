import type { Metadata } from "next";

import { PolicyView } from "@/components/legal/policy-view";
import { buildPageMetadata } from "@/lib/metadata";

import { normalizedPolicies } from "../normalized-content";

export const metadata: Metadata = buildPageMetadata(
  "Security",
  "How NewsIQ protects its service and your data, what it does not have yet, and how to report a vulnerability.",
  "/security"
);

export default function SecurityPage() {
  return <PolicyView doc={normalizedPolicies.security} current="/security" />;
}
