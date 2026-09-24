import type { Metadata } from "next";
import Link from "next/link";

import { LegalNav } from "@/components/legal/policy-view";
import { buildPageMetadata } from "@/lib/metadata";
import { SITE } from "@/lib/site-identity";

export const metadata: Metadata = buildPageMetadata(
  "Contact & Grievances",
  "How to reach NewsIQ for support, privacy requests, copyright notices, security reports and grievances.",
  "/contact"
);

const ROUTES: { need: string; how: React.ReactNode; reply: string }[] = [
  {
    need: "General questions and support",
    how: <Link href="/legal?policy=contact-form">Contact form</Link>,
    reply: "Within 7 days",
  },
  {
    need: "Privacy requests (access, correction, erasure, nomination)",
    how: (
      <>
        <Link href="/settings">Settings</Link> for export and deletion, or the{" "}
        <Link href="/legal?policy=privacy-form">Privacy Rights form</Link>
      </>
    ),
    reply: "Within 30 days",
  },
  {
    need: "Grievances",
    how: <>Email the Grievance Officer (below)</>,
    reply: "Acknowledged within 24 hours, resolved within 15 days",
  },
  {
    need: "Copyright notices",
    how: <Link href="/legal?policy=dmca-form">Copyright form</Link>,
    reply: "Acknowledged within 24 hours, decided within 15 days",
  },
  {
    need: "Security vulnerabilities",
    how: <>Email with &quot;Security&quot; in the subject (see <Link href="/security">Security</Link>)</>,
    reply: "Acknowledged within 72 hours",
  },
];

export default function ContactPage() {
  return (
    <div className="legal-layout">
      <LegalNav current="/contact" />

      <main className="doc-col" id="main-content">
        <div className="doc-hero">
          <div className="doc-eyebrow">NewsIQ Legal</div>
          <h1 className="doc-title">Contact &amp; Grievances</h1>
          <p className="doc-subtitle">
            NewsIQ is operated by {SITE.operator}, {SITE.operatorDescription}. Every request reaches the same
            monitored inbox.
          </p>
        </div>

        <section className="sec" id="inbox">
          <h2 className="sec-title">Email</h2>
          <div className="prose">
            <p>
              <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>
            </p>
          </div>
        </section>

        <section className="sec" id="grievance-officer">
          <h2 className="sec-title">Grievance Officer</h2>
          <div className="prose">
            <p>
              {SITE.grievanceOfficer}, {SITE.country}. Email{" "}
              <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a> with &quot;Grievance&quot; in the
              subject. Grievances are acknowledged within 24 hours and resolved within 15 days.
            </p>
          </div>
        </section>

        <section className="sec" id="routes">
          <h2 className="sec-title">Where to send what</h2>
          <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: "var(--r8)" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13.5px", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "2px solid var(--border)" }}>
                  <th scope="col" style={{ padding: "10px 12px" }}>For</th>
                  <th scope="col" style={{ padding: "10px 12px" }}>Use</th>
                  <th scope="col" style={{ padding: "10px 12px" }}>We reply</th>
                </tr>
              </thead>
              <tbody>
                {ROUTES.map((r) => (
                  <tr key={r.need} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px 12px" }}>{r.need}</td>
                    <td style={{ padding: "10px 12px" }}>{r.how}</td>
                    <td style={{ padding: "10px 12px" }}>{r.reply}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="doc-footer">
          <div style={{ fontSize: "13px", color: "var(--ink3)" }}>
            © {new Date().getFullYear()} {SITE.name} · operated by {SITE.operator}, {SITE.country}
          </div>
        </div>
      </main>

      <aside className="meta-col" aria-label="Related">
        <div className="meta-card">
          <div className="meta-card-title">Related</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12.5px" }}>
            <Link href="/privacy">Privacy Policy</Link>
            <Link href="/tos">Terms of Service</Link>
            <Link href="/security">Security</Link>
          </div>
        </div>
      </aside>
    </div>
  );
}
