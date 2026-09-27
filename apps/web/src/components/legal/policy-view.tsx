import Link from "next/link";
import { Fragment } from "react";

import type { PolicyDocument, StorageItem } from "@/app/(legal)/normalized-content";
import { SITE } from "@/lib/site-identity";

/**
 * A policy rendered on the server.
 *
 * The Legal Center at /legal is a client component driven by ?policy=, so
 * its HTML carried only "Loading legal center..." and /privacy and /tos were
 * JavaScript redirects to it. A crawler, a link preview, or a reviewer
 * fetching the page without JavaScript saw no policy at all. These pages put
 * the full text in the HTML.
 */
export const POLICY_PAGES: { href: string; label: string }[] = [
  { href: "/tos", label: "Terms of Service" },
  { href: "/privacy", label: "Privacy Policy" },
  { href: "/cookies", label: "Cookie Policy" },
  { href: "/security", label: "Security" },
  { href: "/contact", label: "Contact & Grievances" },
  { href: "/legal", label: "All policies & request forms" },
];

export function LegalNav({ current }: { current: string }) {
  return (
    <nav className="toc-col" aria-label="Legal pages">
      <div className="toc-header">Legal</div>
      <ul className="toc-list">
        {POLICY_PAGES.map((p) => (
          <li key={p.href}>
            <Link
              href={p.href}
              className={`toc-item ${current === p.href ? "active" : ""}`}
              aria-current={current === p.href ? "page" : undefined}
            >
              <span className="toc-num">●</span>
              {p.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** A storage key that wraps after "_" and "," instead of mid-word. */
function BreakableKey({ name }: { name: string }) {
  const parts = name.replace(/([_,])/g, "$1\u0000").split("\u0000");
  return (
    <>
      {parts.map((part, i) => (
        <Fragment key={i}>
          {part}
          {i < parts.length - 1 && <wbr />}
        </Fragment>
      ))}
    </>
  );
}

/**
 * The cookie and browser-storage inventory, shared by /cookies and the Legal
 * Center. Seven columns became five: the storage type sits under the name,
 * the consent rule under the category, and "Third party: No" reads as the
 * provider. On a phone each row becomes a labelled card.
 */
export function StorageTable({
  items,
  title = "Everything we store in your browser",
}: {
  items: StorageItem[];
  title?: string;
}) {
  return (
    <section className="sec" id="storage-inventory">
      <h2 className="sec-title">{title}</h2>
      <div className="table-wrap">
        <table className="data-table storage-table">
          <thead>
            <tr>
              {["Name", "Purpose", "Category", "Kept for", "Provider"].map((h) => (
                <th key={h} scope="col">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.name}>
                <td data-label="Name">
                  <div>
                    <code className="st-name">
                      <BreakableKey name={row.name} />
                    </code>
                    <span className="st-kind">{row.kind}</span>
                  </div>
                </td>
                <td data-label="Purpose">
                  <div>{row.purpose}</div>
                </td>
                <td data-label="Category">
                  <div>
                    <span className={`st-badge st-${row.category.toLowerCase()}`}>{row.category}</span>
                    <span className={`st-consent ${row.needsConsent ? "st-needs-consent" : ""}`}>
                      {row.needsConsent ? "Only with your consent" : "No consent needed"}
                    </span>
                  </div>
                </td>
                <td data-label="Kept for">
                  <div>{row.retention}</div>
                </td>
                <td data-label="Provider">
                  <div>{row.thirdParty === "No" ? "NewsIQ" : row.thirdParty}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function PolicyView({
  doc,
  current,
  children,
}: {
  doc: PolicyDocument;
  current: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="legal-layout">
      <LegalNav current={current} />

      <main className="doc-col" id="main-content">
        <div className="doc-hero">
          <div className="doc-eyebrow">NewsIQ Legal</div>
          <h1 className="doc-title">{doc.title}</h1>
          <p className="doc-subtitle">{doc.subtitle}</p>
          <div className="doc-meta-pills">
            <span className="doc-pill">Effective {doc.effectiveDate}</span>
            <span className="doc-pill ver-badge">Version {doc.version}</span>
            {doc.lawContext && <span className="doc-pill">{doc.lawContext}</span>}
          </div>
        </div>

        {doc.sections.map((sec, idx) => (
          <section className="sec" id={sec.id} key={sec.id}>
            <div className="sec-num">
              <span>{String(idx + 1).padStart(2, "0")}</span>
            </div>
            <h2 className="sec-title">{sec.title}</h2>
            <div className="prose">
              <p>{sec.content}</p>
            </div>
          </section>
        ))}

        {children}

        <div className="doc-footer">
          <div style={{ fontSize: "13px", color: "var(--ink3)" }}>
            © {new Date().getFullYear()} {SITE.legalName} ·{" "}
            <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>
          </div>
        </div>
      </main>

      <aside className="meta-col" aria-label="On this page">
        <div className="meta-card">
          <div className="meta-card-title">On this page</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {doc.sections.map((sec, idx) => (
              <a key={sec.id} href={`#${sec.id}`} style={{ fontSize: "12px", color: "var(--ink3)", textDecoration: "none", padding: "3px 0" }}>
                <span style={{ marginRight: "6px", fontSize: "10px", opacity: 0.7 }}>
                  {String(idx + 1).padStart(2, "0")}
                </span>
                {sec.title}
              </a>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}
