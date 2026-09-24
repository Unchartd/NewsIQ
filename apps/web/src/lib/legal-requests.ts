import apiClient from "@/lib/api-client";
import { SITE } from "@/lib/site-identity";

export type LegalRequestKind = "privacy" | "copyright" | "abuse" | "contact";

export interface LegalRequestPayload {
  kind: LegalRequestKind;
  email: string;
  details: string;
  name?: string;
  subject?: string;
  request_type?: string;
  reference_url?: string;
  /** Honeypot — always empty for real users. */
  website?: string;
}

/**
 * Deliver a legal, privacy, copyright, abuse or contact request.
 *
 * These forms used to show "submitted successfully" and send nothing. Every
 * request now goes to the API, which emails it to the monitored inbox and
 * returns a reference number, or fails loudly.
 */
export async function submitLegalRequest(payload: LegalRequestPayload): Promise<string> {
  const res = await apiClient.post("/legal/requests", payload);
  return res.data.reference as string;
}

/** A message that always leaves the person a way to reach us. */
export function legalRequestErrorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Please check the form: some fields are missing or too short.";
  return `Your request could not be sent. Please email ${SITE.contactEmail} directly.`;
}
