import type { Metadata } from "next";

import { PolicyView } from "@/components/legal/policy-view";
import { buildPageMetadata } from "@/lib/metadata";

import { normalizedPolicies } from "../normalized-content";

export const metadata: Metadata = buildPageMetadata(
  "Terms of Service",
  "The terms for using NewsIQ, the AI news platform that turns coverage from many outlets into one clear story.",
  "/tos"
);

export default function TermsPage() {
  return <PolicyView doc={normalizedPolicies.tos} current="/tos" />;
}
