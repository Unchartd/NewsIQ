"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";

export default function PrivacyPage() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const id = e.target.id;
            document.querySelectorAll(".toc-item").forEach((i) => {
              i.classList.remove("active");
              if (i.getAttribute("href") === "#" + id) i.classList.add("active");
            });
          }
        });
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
    );

    document.querySelectorAll(".sec").forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  const handleDownload = () => {
    toast.success("Downloading PDF...");
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success("Link copied to clipboard");
  };

  return (
    <div className="legal-layout">
      {/* ── LEFT TOC ── */}
      <nav className="toc-col">
        <div className="toc-header">Contents</div>
        <ul className="toc-list">
          <li><a className="toc-item active" href="#pp-1"><span className="toc-num">01</span>Overview</a></li>
          <li><a className="toc-item" href="#pp-2"><span className="toc-num">02</span>Data We Collect</a></li>
          <li><a className="toc-item" href="#pp-3"><span className="toc-num">03</span>How We Use Data</a></li>
          <li><a className="toc-item" href="#pp-4"><span className="toc-num">04</span>Legal Bases</a></li>
          <li><a className="toc-item" href="#pp-5"><span className="toc-num">05</span>Sharing & Disclosure</a></li>
          <li><a className="toc-item" href="#pp-6"><span className="toc-num">06</span>Cookies</a></li>
          <li><a className="toc-item" href="#pp-7"><span className="toc-num">07</span>Data Retention</a></li>
          <li><a className="toc-item" href="#pp-8"><span className="toc-num">08</span>Your Rights</a></li>
          <li><a className="toc-item" href="#pp-9"><span className="toc-num">09</span>Security</a></li>
          <li><a className="toc-item" href="#pp-10"><span className="toc-num">10</span>Children</a></li>
          <li><a className="toc-item" href="#pp-11"><span className="toc-num">11</span>International Transfers</a></li>
          <li><a className="toc-item" href="#pp-12"><span className="toc-num">12</span>Changes</a></li>
          <li><a className="toc-item" href="#pp-13"><span className="toc-num">13</span>Contact</a></li>
        </ul>
        <div className="toc-divider"></div>
        <Link href="/tos" className="toc-item">
          <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-doc" /></svg>
          Terms of Service
        </Link>
      </nav>

      {/* ── MAIN DOC ── */}
      <div className="doc-col">
        {/* Hero */}
        <div className="doc-hero">
          <div className="doc-eyebrow"><svg width="14" height="14"><use href="#i-shield" /></svg>NewsIQ Legal</div>
          <h1 className="doc-title">Privacy Policy</h1>
          <p className="doc-subtitle">We built NewsIQ to give you understanding, not extract your attention. This policy explains exactly what data we collect, why, and what control you have over it.</p>
          <div className="doc-meta-pills">
            <span className="doc-pill">📅 Effective: June 16, 2025</span>
            <span className="doc-pill">🔄 Last updated: June 16, 2026</span>
            <span className="doc-pill ver-badge">v2.1</span>
            <button className="doc-pill" style={{ cursor: "pointer", border: "1px solid var(--border)", background: "var(--surface)" }} onClick={handleDownload}>
              <svg width="11" height="11"><use href="#i-download" /></svg>Download PDF
            </button>
          </div>
        </div>

        {/* Plain-English Summary */}
        <div className="summary-banner">
          <div className="summary-banner-title">✦ The Short Version</div>
          <div className="summary-grid">
            <div className="summary-item">
              <div className="summary-item-icon">🚫</div>
              <div className="summary-item-text"><strong>No selling your data</strong>We never sell personal data to advertisers, data brokers, or third parties. Full stop.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🎯</div>
              <div className="summary-item-text"><strong>Personalisation only</strong>Reading history is used to improve your feed — nothing else.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🍪</div>
              <div className="summary-item-text"><strong>Minimal cookies</strong>Only essential and analytics cookies. No advertising trackers.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🗑️</div>
              <div className="summary-item-text"><strong>Delete anytime</strong>Request full account and data deletion at any time. Processed within 30 days.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🔒</div>
              <div className="summary-item-text"><strong>Encrypted in transit & at rest</strong>All data uses TLS 1.3 in transit and AES-256 at rest.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">📧</div>
              <div className="summary-item-text"><strong>DPDP Act compliant</strong>Governed by India&apos;s Digital Personal Data Protection Act, 2023.</div>
            </div>
          </div>
        </div>

        {/* Section 1 */}
        <div className="sec" id="pp-1">
          <div className="sec-num"><span>01</span></div>
          <h2 className="sec-title">Overview & Who We Are</h2>
          <div className="prose">
            <p>This Privacy Policy explains how <strong>NewsIQ Technologies Private Limited</strong> (&quot;NewsIQ&quot;, &quot;we&quot;, &quot;us&quot;) collects, uses, discloses, and safeguards information when you use the NewsIQ platform.</p>
            <p>We act as the <strong>Data Fiduciary</strong> (as defined under the Digital Personal Data Protection Act, 2023) in respect of personal data you provide directly to us. For data processed on behalf of Enterprise customers, we may act as Data Processor.</p>
            <p>This policy applies to all NewsIQ services: the web application at newsiq.in, mobile applications (if any), browser extensions, the API, and the Daily Digest email service.</p>
            <div className="callout callout-green">
              <span className="callout-icon">🛡️</span>
              <div className="callout-body"><strong>Our core privacy commitment:</strong> NewsIQ is an ad-free service. We do not monetise your data, build advertising profiles, or share personal information with advertising networks.</div>
            </div>
          </div>
        </div>

        {/* Section 2 */}
        <div className="sec" id="pp-2">
          <div className="sec-num"><span>02</span></div>
          <h2 className="sec-title">Data We Collect</h2>
          <div className="prose">
            <p>We collect only the data necessary to provide and improve the Service:</p>
            <table className="data-table">
              <thead><tr><th>Category</th><th>Data points</th><th>Collected when</th><th>Required?</th></tr></thead>
              <tbody>
                <tr>
                  <td className="td-cat">Account data</td>
                  <td>Name, email address, password hash, OAuth provider ID</td>
                  <td>Account creation</td>
                  <td>Yes</td>
                </tr>
                <tr>
                  <td className="td-cat">Profile data</td>
                  <td>Display name, bio, phone number, profile photo</td>
                  <td>Profile setup</td>
                  <td>No</td>
                </tr>
                <tr>
                  <td className="td-cat">Preferences</td>
                  <td>Selected topics, locations, summary depth, theme, digest schedule</td>
                  <td>Onboarding & settings</td>
                  <td>No</td>
                </tr>
                <tr>
                  <td className="td-cat">Reading activity</td>
                  <td>Story IDs opened, time on story, summary depth used, bookmarks</td>
                  <td>Using the Service</td>
                  <td>No (opt-out available)</td>
                </tr>
                <tr>
                  <td className="td-cat">Usage telemetry</td>
                  <td>Feature clicks, scroll depth, search queries, errors encountered</td>
                  <td>Using the Service</td>
                  <td>No (opt-out available)</td>
                </tr>
                <tr>
                  <td className="td-cat">Device & network</td>
                  <td>IP address (truncated), browser user-agent, screen resolution, time zone</td>
                  <td>Each session</td>
                  <td>Yes (security)</td>
                </tr>
                <tr>
                  <td className="td-cat">Billing data</td>
                  <td>Payment method type, last 4 digits, billing address (Pro users)</td>
                  <td>Subscription purchase</td>
                  <td>Pro only</td>
                </tr>
                <tr>
                  <td className="td-cat">Communications</td>
                  <td>Support emails, feedback submitted via the app</td>
                  <td>Contacting us</td>
                  <td>No</td>
                </tr>
              </tbody>
            </table>
            <p>We do not collect: full payment card numbers (handled by Razorpay), government IDs, biometric data, or precise GPS location.</p>
            <div className="callout callout-blue">
              <span className="callout-icon">ℹ️</span>
              <div className="callout-body"><strong>IP address truncation:</strong> We store only the first two octets of your IP address (e.g. 192.168.x.x) for security logging, making individual identification impossible from logs alone.</div>
            </div>
          </div>
        </div>

        {/* Section 3 */}
        <div className="sec" id="pp-3">
          <div className="sec-num"><span>03</span></div>
          <h2 className="sec-title">How We Use Your Data</h2>
          <div className="prose">
            <p>We use personal data for the following specific purposes and no others:</p>
            <ul>
              <li><strong>Service delivery</strong> — Authenticate your account, deliver your Daily Digest, sync bookmarks across devices, and surface personalised story recommendations.</li>
              <li><strong>Feed personalisation</strong> — Use your topic preferences, location settings, and reading history to weight which stories appear at the top of your feed. This processing is entirely on-platform; no data is shared with external recommendation engines.</li>
              <li><strong>Product improvement</strong> — Aggregate, anonymised usage telemetry helps us understand feature adoption, identify bugs, and prioritise roadmap decisions. Individual-level data is not used for this purpose.</li>
              <li><strong>Security & fraud prevention</strong> — Session data and truncated IP addresses are retained for 30 days to detect and prevent account compromise, abuse, and unauthorised scraping.</li>
              <li><strong>Billing</strong> — Process subscription payments via Razorpay and send receipts. Full payment data is handled by Razorpay and not stored on NewsIQ systems.</li>
              <li><strong>Legal compliance</strong> — Respond to lawful requests from Indian authorities as required under applicable law.</li>
            </ul>
            <div className="callout callout-red">
              <span className="callout-icon">🚫</span>
              <div className="callout-body"><strong>We never use your data for:</strong> Targeted advertising, sale to third parties, profiling for political or religious purposes, or training external AI models.</div>
            </div>
          </div>
        </div>

        {/* Section 4 */}
        <div className="sec" id="pp-4">
          <div className="sec-num"><span>04</span></div>
          <h2 className="sec-title">Legal Bases for Processing</h2>
          <div className="prose">
            <p>Under the Digital Personal Data Protection Act, 2023 (DPDP Act), we process personal data on the following legal bases:</p>
            <div className="def-list">
              <div className="def-row"><div className="def-term">Consent</div><div className="def-desc">Reading activity tracking, analytics participation, marketing emails. You may withdraw consent at any time from Settings → Privacy.</div></div>
              <div className="def-row"><div className="def-term">Contract</div><div className="def-desc">Account management, subscription billing, and Digest delivery — necessary to perform the contract between you and NewsIQ.</div></div>
              <div className="def-row"><div className="def-term">Legitimate interest</div><div className="def-desc">Security monitoring, bug detection, and abuse prevention, where our interests do not override your rights.</div></div>
              <div className="def-row"><div className="def-term">Legal obligation</div><div className="def-desc">Retaining billing records and responding to lawful government requests.</div></div>
            </div>
          </div>
        </div>

        {/* Section 5 */}
        <div className="sec" id="pp-5">
          <div className="sec-num"><span>05</span></div>
          <h2 className="sec-title">Sharing & Disclosure</h2>
          <div className="prose">
            <p>We share personal data only in the following limited circumstances:</p>
            <table className="data-table">
              <thead><tr><th>Recipient</th><th>Data shared</th><th>Purpose</th><th>Safeguards</th></tr></thead>
              <tbody>
                <tr><td className="td-cat">Razorpay</td><td>Email, billing address, payment info</td><td>Payment processing</td><td>RBI-regulated, PCI-DSS</td></tr>
                <tr><td className="td-cat">AWS (Mumbai)</td><td>All platform data</td><td>Hosting & storage</td><td>ISO 27001, SOC 2 Type II</td></tr>
                <tr><td className="td-cat">Postmark</td><td>Email address</td><td>Transactional email delivery</td><td>DPA in place</td></tr>
                <tr><td className="td-cat">Sentry</td><td>Anonymised error traces</td><td>Error monitoring</td><td>No PII in traces</td></tr>
                <tr><td className="td-cat">Legal authorities</td><td>As required by law</td><td>Legal compliance</td><td>Minimum necessary; notified if permitted</td></tr>
              </tbody>
            </table>
            <p>We do <strong>not</strong> share data with social media platforms, advertising networks, data brokers, or analytics companies beyond those listed above.</p>
          </div>
        </div>

        {/* Section 6 */}
        <div className="sec" id="pp-6">
          <div className="sec-num"><span>06</span></div>
          <h2 className="sec-title">Cookies & Local Storage</h2>
          <div className="prose">
            <p>We use cookies and browser local storage sparingly. Below is a full inventory:</p>
            <table className="data-table">
              <thead><tr><th>Name</th><th>Type</th><th>Expiry</th><th>Purpose</th></tr></thead>
              <tbody>
                <tr><td className="td-cat">niq_session</td><td><span className="cookie-dot" style={{ background: "#1D4ED8" }}></span>Essential</td><td>Session</td><td>Authentication session token</td></tr>
                <tr><td className="td-cat">niq_theme</td><td><span className="cookie-dot" style={{ background: "#1D4ED8" }}></span>Essential</td><td>1 year</td><td>Light/dark mode preference</td></tr>
                <tr><td className="td-cat">niq_prefs</td><td><span className="cookie-dot" style={{ background: "#1D4ED8" }}></span>Essential</td><td>1 year</td><td>Summary depth, layout preferences</td></tr>
                <tr><td className="td-cat">niq_analytics</td><td><span className="cookie-dot" style={{ background: "#D97706" }}></span>Analytics</td><td>90 days</td><td>Anonymous usage telemetry (opt-out available)</td></tr>
                <tr><td className="td-cat">niq_ab</td><td><span className="cookie-dot" style={{ background: "#D97706" }}></span>Analytics</td><td>30 days</td><td>A/B test bucket assignment</td></tr>
              </tbody>
            </table>
            <div className="callout callout-green">
              <span className="callout-icon">🍪</span>
              <div className="callout-body"><strong>No advertising cookies.</strong> NewsIQ sets zero third-party advertising or tracking cookies. We do not participate in cross-site tracking networks.</div>
            </div>
            <p>You may disable non-essential cookies at any time via <strong>Settings → Privacy → Clear personalisation data</strong>, or through your browser settings. Note that disabling essential cookies will prevent login from functioning.</p>
          </div>
        </div>

        {/* Section 7 */}
        <div className="sec" id="pp-7">
          <div className="sec-num"><span>07</span></div>
          <h2 className="sec-title">Data Retention</h2>
          <div className="prose">
            <div className="def-list">
              <div className="def-row"><div className="def-term">Account data</div><div className="def-desc">Retained for the lifetime of the account, plus 30 days following deletion request to allow recovery.</div></div>
              <div className="def-row"><div className="def-term">Reading history</div><div className="def-desc">Retained for 12 months on a rolling basis, then deleted automatically. You may clear it at any time in Settings.</div></div>
              <div className="def-row"><div className="def-term">Digest emails</div><div className="def-desc">Email delivery logs (recipient, timestamp, open status) retained for 90 days for delivery diagnostics.</div></div>
              <div className="def-row"><div className="def-term">Security logs</div><div className="def-desc">Truncated IP, session IDs, and auth events retained for 30 days.</div></div>
              <div className="def-row"><div className="def-term">Billing records</div><div className="def-desc">Retained for 7 years as required by the Companies Act, 2013.</div></div>
              <div className="def-row"><div className="def-term">Support tickets</div><div className="def-desc">Retained for 2 years, then permanently deleted.</div></div>
            </div>
          </div>
        </div>

        {/* Section 8 */}
        <div className="sec" id="pp-8">
          <div className="sec-num"><span>08</span></div>
          <h2 className="sec-title">Your Rights</h2>
          <div className="prose">
            <p>Under the DPDP Act 2023 and general privacy best practice, you have the following rights with respect to your personal data:</p>
          </div>
          <div className="rights-grid">
            <div className="right-card">
              <div className="right-icon"><svg width="18" height="18" style={{ color: "var(--blue)" }}><use href="#i-eye" /></svg></div>
              <div className="right-title">Right to Access</div>
              <div className="right-desc">Request a copy of all personal data we hold about you. Fulfilled within 72 hours.</div>
            </div>
            <div className="right-card">
              <div className="right-icon"><svg width="18" height="18" style={{ color: "var(--blue)" }}><use href="#i-download" /></svg></div>
              <div className="right-title">Right to Portability</div>
              <div className="right-desc">Download your bookmarks, preferences, and reading history as a JSON file from Settings → Privacy.</div>
            </div>
            <div className="right-card">
              <div className="right-icon">✏️</div>
              <div className="right-title">Right to Correction</div>
              <div className="right-desc">Update incorrect personal data at any time from Settings → Edit Profile.</div>
            </div>
            <div className="right-card">
              <div className="right-icon"><svg width="18" height="18" style={{ color: "var(--err)" }}><use href="#i-trash" /></svg></div>
              <div className="right-title">Right to Erasure</div>
              <div className="right-desc">Request full deletion of your account and data. Processed within 30 days. Billing records retained per legal obligation.</div>
            </div>
            <div className="right-card">
              <div className="right-icon">🚫</div>
              <div className="right-title">Right to Restrict</div>
              <div className="right-desc">Opt out of reading-history tracking and analytics cookies without deleting your account.</div>
            </div>
            <div className="right-card">
              <div className="right-icon"><svg width="18" height="18" style={{ color: "var(--amber)" }}><use href="#i-alert" /></svg></div>
              <div className="right-title">Right to Complain</div>
              <div className="right-desc">Lodge a complaint with the Data Protection Board of India if you believe we have mishandled your data.</div>
            </div>
          </div>
          <div className="prose" style={{ marginTop: "16px" }}>
            <p>To exercise any of these rights, contact <strong>privacy@newsiq.in</strong> or use the self-service controls at Settings → Privacy. We respond to all privacy requests within <strong>72 hours</strong> and fulfil them within <strong>30 days</strong>.</p>
          </div>
        </div>

        {/* Section 9 */}
        <div className="sec" id="pp-9">
          <div className="sec-num"><span>09</span></div>
          <h2 className="sec-title">Security Measures</h2>
          <div className="prose">
            <p>We implement the following technical and organisational security measures:</p>
            <ul>
              <li><strong>Encryption in transit:</strong> TLS 1.3 on all connections. HTTP Strict Transport Security enforced.</li>
              <li><strong>Encryption at rest:</strong> AES-256 encryption for all databases and backups hosted on AWS Mumbai.</li>
              <li><strong>Password storage:</strong> Passwords hashed using bcrypt with a cost factor of 12. We never store plaintext passwords.</li>
              <li><strong>Access control:</strong> Role-based access control (RBAC) for internal systems. Only 3 engineers have production database access, using hardware MFA.</li>
              <li><strong>Penetration testing:</strong> Annual third-party pen test. Results summarised at security.newsiq.in.</li>
              <li><strong>Incident response:</strong> We notify affected users within 72 hours of becoming aware of a confirmed data breach that poses a risk to your rights.</li>
            </ul>
            <div className="callout callout-amber">
              <span className="callout-icon">⚠️</span>
              <div className="callout-body">No method of transmission over the internet or electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your data, we cannot guarantee absolute security.</div>
            </div>
          </div>
        </div>

        {/* Section 10 */}
        <div className="sec" id="pp-10">
          <div className="sec-num"><span>10</span></div>
          <h2 className="sec-title">Children&apos;s Privacy</h2>
          <div className="prose">
            <p>The Service is not directed to children under 13 years of age. We do not knowingly collect personal data from children under 13. If you are a parent or guardian and believe that your child has provided us with personal information, please contact us immediately at <strong>privacy@newsiq.in</strong>.</p>
            <p>For users aged 13 to 18, we require verifiable parental consent and apply the following additional protections:</p>
            <ul>
              <li>Reading history and usage telemetry are disabled by default.</li>
              <li>No marketing emails are sent.</li>
              <li>Pro subscription requires parent/guardian billing confirmation.</li>
            </ul>
          </div>
        </div>

        {/* Section 11 */}
        <div className="sec" id="pp-11">
          <div className="sec-num"><span>11</span></div>
          <h2 className="sec-title">International Data Transfers</h2>
          <div className="prose">
            <p>All primary personal data is stored on AWS infrastructure in the <strong>ap-south-1 (Mumbai) region</strong> within India. No cross-border transfer of Indian user personal data occurs under normal operations.</p>
            <p>Limited data may be processed outside India in the following circumstances:</p>
            <ul>
              <li><strong>Error monitoring (Sentry)</strong> — Anonymised error traces with no PII are processed on Sentry servers in the US.</li>
              <li><strong>Email delivery (Postmark)</strong> — Your email address and digest content are transmitted to Postmark for delivery. Postmark maintains a Data Processing Agreement and complies with applicable transfer mechanisms.</li>
            </ul>
            <p>We will update this section immediately if additional cross-border transfers become necessary, and we will obtain fresh consent where required under the DPDP Act.</p>
          </div>
        </div>

        {/* Section 12 */}
        <div className="sec" id="pp-12">
          <div className="sec-num"><span>12</span></div>
          <h2 className="sec-title">Changes to This Policy</h2>
          <div className="prose">
            <p>We may update this Privacy Policy to reflect changes in our data practices or applicable law. When we make material changes we will:</p>
            <ul>
              <li>Update the &quot;Last updated&quot; date at the top of this page.</li>
              <li>Send an email to all registered users at least <strong>14 days before</strong> changes take effect.</li>
              <li>Display a prominent in-app banner for 30 days.</li>
              <li>Request fresh consent where the change affects previously consented-to processing.</li>
            </ul>
            <p>All previous versions of this policy are archived and available upon request at <strong>privacy@newsiq.in</strong>.</p>
          </div>
        </div>

        {/* Section 13 */}
        <div className="sec" id="pp-13">
          <div className="sec-num"><span>13</span></div>
          <h2 className="sec-title">Contact & Data Grievance Officer</h2>
          <div className="prose">
            <p>In accordance with the Information Technology Act, 2000 and the DPDP Act 2023, the name and contact details of the Grievance Officer are provided below:</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "16px" }}>
            <div className="contact-chip">
              <div className="chip-icon" style={{ background: "rgba(124,58,237,.1)" }}><svg width="15" height="15" style={{ color: "#7C3AED" }}><use href="#i-user" /></svg></div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Grievance Officer</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>Aarav Mehta — CEO, NewsIQ Technologies Pvt Ltd</div>
              </div>
            </div>
            <div className="contact-chip" onClick={() => toast.info("Opening email client...")}>
              <div className="chip-icon" style={{ background: "rgba(196,30,58,.1)" }}><svg width="15" height="15" style={{ color: "var(--primary)" }}><use href="#i-mail" /></svg></div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Privacy Requests</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>privacy@newsiq.in · Response within 72 hours</div>
              </div>
            </div>
            <div className="contact-chip" onClick={() => toast.info("Opening email client...")}>
              <div className="chip-icon" style={{ background: "rgba(22,163,74,.1)" }}><svg width="15" height="15" style={{ color: "var(--green)" }}><use href="#i-shield" /></svg></div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Security Disclosures</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>security@newsiq.in · PGP key available at security.newsiq.in</div>
              </div>
            </div>
            <div className="contact-chip">
              <div className="chip-icon" style={{ background: "rgba(107,107,107,.1)" }}>🏢</div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Registered Address</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>NewsIQ Technologies Pvt Ltd, 4th Floor, Brigade Road, Bengaluru – 560025, Karnataka, India</div>
              </div>
            </div>
          </div>

          {/* Data export CTA */}
          <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--r10)", padding: "20px", marginTop: "24px", display: "flex", alignItems: "center", gap: "16px", flexWrap: "wrap" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "15px", fontWeight: 600, color: "var(--ink)", marginBottom: "4px" }}>Exercise your data rights</div>
              <div style={{ fontSize: "13px", color: "var(--ink3)" }}>Download your data, clear your history, or request full account deletion — all from Settings.</div>
            </div>
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
              <button className="btnp" onClick={() => toast.info("Opening Settings → Privacy...")}>
                <svg width="13" height="13"><use href="#i-download" /></svg>Download my data
              </button>
              <button className="btno" onClick={() => toast.info("Opening Settings → Account...")} style={{ fontSize: "13px", padding: "9px 16px" }}>
                Delete account
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="doc-footer">
          <div style={{ fontSize: "13px", color: "var(--ink3)" }}>© 2026 NewsIQ Technologies Private Limited. All rights reserved.</div>
          <div className="doc-footer-nav">
            <Link href="/tos" className="doc-footer-link">Terms of Service</Link>
            <span className="doc-footer-link" onClick={() => toast.info("Opening cookie settings...")}>Cookie Settings</span>
            <span className="doc-footer-link" onClick={handleDownload}>Download PDF</span>
          </div>
        </div>
      </div>

      {/* ── RIGHT META ── */}
      <div className="meta-col">
        <div className="meta-card">
          <div className="meta-card-title">Document Info</div>
          <div className="meta-row"><span className="meta-lbl">Version</span><span className="meta-val">2.1</span></div>
          <div className="meta-row"><span className="meta-lbl">Effective</span><span className="meta-val">Jun 16, 2025</span></div>
          <div className="meta-row"><span className="meta-lbl">Updated</span><span className="meta-val">Jun 16, 2026</span></div>
          <div className="meta-row"><span className="meta-lbl">Law</span><span className="meta-val">DPDP Act 2023</span></div>
          <div className="meta-row"><span className="meta-lbl">Data host</span><span className="meta-val">AWS Mumbai</span></div>
        </div>
        <div className="meta-card">
          <div className="meta-card-title">Data Promises</div>
          <div className="meta-row"><span style={{ color: "var(--green)", fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}><svg width="13" height="13"><use href="#i-check" /></svg>No data selling</span></div>
          <div className="meta-row"><span style={{ color: "var(--green)", fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}><svg width="13" height="13"><use href="#i-check" /></svg>No ad tracking</span></div>
          <div className="meta-row"><span style={{ color: "var(--green)", fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}><svg width="13" height="13"><use href="#i-check" /></svg>India-only storage</span></div>
          <div className="meta-row"><span style={{ color: "var(--green)", fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}><svg width="13" height="13"><use href="#i-check" /></svg>AES-256 encryption</span></div>
          <div className="meta-row" style={{ borderBottom: "none" }}><span style={{ color: "var(--green)", fontSize: "13px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}><svg width="13" height="13"><use href="#i-check" /></svg>72h deletion right</span></div>
        </div>
        <div className="meta-card">
          <div className="meta-card-title">Quick Actions</div>
          <div className="meta-link" onClick={handleDownload}><svg width="13" height="13"><use href="#i-download" /></svg>Download PDF</div>
          <Link href="/tos" className="meta-link"><svg width="13" height="13"><use href="#i-doc" /></svg>Terms of Service</Link>
          <div className="meta-link" onClick={handleCopyLink}><svg width="13" height="13"><use href="#i-copy" /></svg>Copy link</div>
          <div className="meta-link" onClick={() => toast.info("Opening Settings → Privacy...")}><svg width="13" height="13"><use href="#i-lock" /></svg>Privacy settings</div>
        </div>
      </div>
    </div>
  );
}
