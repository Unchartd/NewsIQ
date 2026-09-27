/**
 * Who operates NewsIQ and how to reach them.
 *
 * The single source for every legal page, footer, contact surface and
 * structured-data block. Legal text must never name a company, person,
 * address or inbox that is not listed here: the pages used to name an
 * invented "NewsIQ Technologies Private Limited", an invented grievance
 * officer, and inboxes on newsiq.ai and newsiq.in — domains this project
 * does not own, so privacy requests and copyright notices went to strangers.
 */
export const SITE = {
  name: "NewsIQ",
  url: "https://newsiq.online",
  /**
   * Named as data fiduciary / controller, party to the Terms and copyright
   * holder. Not incorporated yet: change this to the registered name (e.g.
   * "NewsIQ Pvt. Ltd.") only once it has a CIN. Trading under "Private
   * Limited" before incorporation is an offence (Companies Act 2013, s. 453).
   */
  legalName: "NewsIQ",
  /** Law governing the Terms. */
  jurisdiction: "India",
  /** The one monitored inbox for support, privacy, legal and security. */
  contactEmail: "hello.newsiq@gmail.com",
  /** Named on the contact page as the IT Rules, 2021 require. */
  grievanceOfficer: "Zakaur Rahman",
  /** Last material revision of the policies. */
  policiesUpdated: "September 27, 2026",
  policiesVersion: "4.1",
} as const;
