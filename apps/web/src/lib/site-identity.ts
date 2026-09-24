/**
 * Who operates NewsIQ and how to reach them.
 *
 * The single source for every legal page, footer, contact surface and
 * structured-data block. Legal text must never name a company, person,
 * address or inbox that is not listed here: the pages used to name an
 * invented "NewsIQ Technologies Private Limited", an invented grievance
 * officer, and inboxes on newsiq.ai and newsiq.in — domains this project
 * does not own, so privacy requests and copyright notices went to strangers.
 *
 * If the operator incorporates, or a domain inbox is set up, change it here.
 */
export const SITE = {
  name: "NewsIQ",
  url: "https://newsiq.online",
  /** The legal operator (data fiduciary / controller). */
  operator: "Zakaur Rahman",
  operatorDescription: "an independent founder based in India",
  country: "India",
  /** The one monitored inbox for support, privacy, legal and security. */
  contactEmail: "hello.newsiq@gmail.com",
  grievanceOfficer: "Zakaur Rahman",
  /** Last material revision of the policies. */
  policiesUpdated: "September 24, 2026",
  policiesVersion: "4.0",
} as const;
