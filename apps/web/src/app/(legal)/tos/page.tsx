"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { toast } from "sonner";

export default function TosPage() {
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
          <li><a className="toc-item active" href="#tos-1"><span className="toc-num">01</span>Agreement</a></li>
          <li><a className="toc-item" href="#tos-2"><span className="toc-num">02</span>Eligibility</a></li>
          <li><a className="toc-item" href="#tos-3"><span className="toc-num">03</span>Account</a></li>
          <li><a className="toc-item" href="#tos-4"><span className="toc-num">04</span>Service</a></li>
          <li><a className="toc-item" href="#tos-5"><span className="toc-num">05</span>Subscriptions</a></li>
          <li><a className="toc-item" href="#tos-6"><span className="toc-num">06</span>Acceptable Use</a></li>
          <li><a className="toc-item" href="#tos-7"><span className="toc-num">07</span>Intellectual Property</a></li>
          <li><a className="toc-item" href="#tos-8"><span className="toc-num">08</span>Third-Party Content</a></li>
          <li><a className="toc-item" href="#tos-9"><span className="toc-num">09</span>Disclaimers</a></li>
          <li><a className="toc-item" href="#tos-10"><span className="toc-num">10</span>Limitation of Liability</a></li>
          <li><a className="toc-item" href="#tos-11"><span className="toc-num">11</span>Termination</a></li>
          <li><a className="toc-item" href="#tos-12"><span className="toc-num">12</span>Governing Law</a></li>
          <li><a className="toc-item" href="#tos-13"><span className="toc-num">13</span>Changes</a></li>
          <li><a className="toc-item" href="#tos-14"><span className="toc-num">14</span>Contact</a></li>
        </ul>
        <div className="toc-divider"></div>
        <Link href="/privacy" className="toc-item">
          <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-shield" /></svg>
          Privacy Policy
        </Link>
      </nav>

      {/* ── MAIN DOC ── */}
      <div className="doc-col" id="tos-top">
        {/* Hero */}
        <div className="doc-hero">
          <div className="doc-eyebrow"><svg width="14" height="14"><use href="#i-doc" /></svg>NewsIQ Legal</div>
          <h1 className="doc-title">Terms of Service</h1>
          <p className="doc-subtitle">Please read these terms carefully. By accessing or using NewsIQ you agree to be bound by everything here.</p>
          <div className="doc-meta-pills">
            <span className="doc-pill">📅 Effective: June 16, 2025</span>
            <span className="doc-pill">🔄 Last updated: June 16, 2026</span>
            <span className="doc-pill ver-badge">v2.1</span>
            <button className="doc-pill" style={{ cursor: "pointer", border: "1px solid var(--border)", background: "var(--surface)" }} onClick={handleDownload}>
              <svg width="11" height="11"><use href="#i-download" /></svg>Download PDF
            </button>
          </div>
        </div>

        {/* Plain-English Summary Banner */}
        <div className="summary-banner">
          <div className="summary-banner-title">✦ Plain-English Summary</div>
          <div className="summary-grid">
            <div className="summary-item">
              <div className="summary-item-icon">🆓</div>
              <div className="summary-item-text"><strong>Free & Pro tiers</strong>Free access is real. Pro unlocks summaries, comparison tools, and AI chat.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">📰</div>
              <div className="summary-item-text"><strong>We summarise, not replace</strong>AI summaries link back to original publishers. We never claim articles as our own.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🚫</div>
              <div className="summary-item-text"><strong>No scraping or bots</strong>You may not automate access to NewsIQ or re-publish our summaries.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">⚠️</div>
              <div className="summary-item-text"><strong>AI isn&apos;t perfect</strong>Summaries are AI-generated and may contain errors. Always verify critical information.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">🇮🇳</div>
              <div className="summary-item-text"><strong>Governed by Indian law</strong>Disputes resolved under the laws of India, courts of Bengaluru.</div>
            </div>
            <div className="summary-item">
              <div className="summary-item-icon">✉️</div>
              <div className="summary-item-text"><strong>Questions?</strong>Email legal@newsiq.in — we respond within 5 business days.</div>
            </div>
          </div>
        </div>

        {/* Section 1 */}
        <div className="sec" id="tos-1">
          <div className="sec-num"><span>01</span></div>
          <h2 className="sec-title">Agreement to Terms</h2>
          <div className="prose">
            <p>These Terms of Service (&quot;Terms&quot;) constitute a legally binding agreement between you (&quot;User&quot;, &quot;you&quot;) and NewsIQ Technologies Private Limited (&quot;NewsIQ&quot;, &quot;we&quot;, &quot;us&quot;, &quot;our&quot;), a company incorporated under the laws of India, governing your access to and use of the NewsIQ platform, including our website at newsiq.in, mobile applications, browser extensions, APIs, and any related services (collectively, the &quot;Service&quot;).</p>
            <p>By creating an account, subscribing to a digest, or simply accessing any part of the Service, you acknowledge that you have read, understood, and agree to be bound by these Terms and our <Link href="/privacy">Privacy Policy</Link>, which is incorporated herein by reference.</p>
            <div className="callout callout-amber">
              <span className="callout-icon">⚠️</span>
              <div className="callout-body"><strong>If you do not agree to these Terms, you must immediately discontinue use of the Service.</strong> If you are using NewsIQ on behalf of an organisation, you represent that you have authority to bind that organisation to these Terms.</div>
            </div>
          </div>
        </div>

        {/* Section 2 */}
        <div className="sec" id="tos-2">
          <div className="sec-num"><span>02</span></div>
          <h2 className="sec-title">Eligibility</h2>
          <div className="prose">
            <p>To use NewsIQ you must be at least <strong>13 years old</strong>. If you are between 13 and 18, you may only use the Service with verifiable parental or guardian consent. By using the Service you represent and warrant that you meet these requirements.</p>
            <p>NewsIQ reserves the right to request proof of age or consent at any time and to suspend or terminate accounts that do not meet eligibility criteria.</p>
            <ul>
              <li>You may not create an account if you have been previously banned from the Service.</li>
              <li>Accounts created using false identity information will be terminated without notice.</li>
              <li>Residents of jurisdictions where access to the Service is prohibited by applicable law may not use NewsIQ.</li>
            </ul>
          </div>
        </div>

        {/* Section 3 */}
        <div className="sec" id="tos-3">
          <div className="sec-num"><span>03</span></div>
          <h2 className="sec-title">Account Registration & Security</h2>
          <div className="prose">
            <p>You may access a limited version of NewsIQ without registering. To unlock personalised feeds, bookmarks, digests, and Pro features, you must create an account by providing a valid email address and creating a password, or by authenticating through a supported third-party provider (Google).</p>
            <p>You are solely responsible for:</p>
            <ul>
              <li>Maintaining the confidentiality of your login credentials.</li>
              <li>All activity that occurs under your account, whether authorised by you or not.</li>
              <li>Notifying us immediately at <strong>security@newsiq.in</strong> if you suspect unauthorised access.</li>
            </ul>
            <div className="callout callout-blue">
              <span className="callout-icon">🔒</span>
              <div className="callout-body">We recommend enabling two-factor authentication in your account settings. NewsIQ will never ask for your password via email.</div>
            </div>
            <p>You may not create more than one personal account or create accounts using automated means. Business or team accounts require an Enterprise subscription.</p>
          </div>
        </div>

        {/* Section 4 */}
        <div className="sec" id="tos-4">
          <div className="sec-num"><span>04</span></div>
          <h2 className="sec-title">Description of the Service</h2>
          <div className="prose">
            <p>NewsIQ is an AI-powered news intelligence platform that ingests articles from third-party publishers and news agencies, clusters related articles into unified story objects, and presents AI-generated summaries, source comparisons, and timelines to users.</p>
            <div className="def-list">
              <div className="def-row"><div className="def-term">Story</div><div className="def-desc">A cluster of related articles representing a single news event or developing situation, with an AI-generated headline, summaries at three depth levels, and a source attribution table.</div></div>
              <div className="def-row"><div className="def-term">AI Summary</div><div className="def-desc">A machine-generated condensation of clustered articles, produced by large language models operated by or contracted to NewsIQ. Marked with the ✦ symbol throughout the interface.</div></div>
              <div className="def-row"><div className="def-term">Difference Engine</div><div className="def-desc">A feature that highlights factual discrepancies, omissions, and contradictions between how different publishers cover the same story.</div></div>
              <div className="def-row"><div className="def-term">Daily Digest</div><div className="def-desc">A scheduled briefing of curated top stories delivered via email, Telegram, or in-app at user-specified times.</div></div>
              <div className="def-row"><div className="def-term">Pro</div><div className="def-desc">The paid subscription tier that unlocks unlimited stories, all summary depths, Difference Engine, personalised feeds, and Daily Digest delivery.</div></div>
            </div>
            <p>NewsIQ does not host or reproduce full article text. All links in Source Coverage tables direct users to the original publisher&apos;s website. We make no representation that third-party URLs will remain accessible.</p>
          </div>
        </div>

        {/* Section 5 */}
        <div className="sec" id="tos-5">
          <div className="sec-num"><span>05</span></div>
          <h2 className="sec-title">Subscriptions & Billing</h2>
          <div className="prose">
            <p>NewsIQ offers the following plans. Pricing is in Indian Rupees (INR) and is inclusive of applicable taxes unless stated otherwise.</p>
            <table className="data-table">
              <thead><tr><th>Plan</th><th>Price</th><th>Billing</th><th>Cancellation</th></tr></thead>
              <tbody>
                <tr><td className="td-cat">Free</td><td>₹0</td><td>N/A</td><td>N/A</td></tr>
                <tr><td className="td-cat">Pro Monthly</td><td>₹399/month</td><td>Monthly on signup date</td><td>Any time; access continues to period end</td></tr>
                <tr><td className="td-cat">Pro Annual</td><td>₹3,499/year</td><td>Annually on signup date</td><td>Any time; no partial refund</td></tr>
                <tr><td className="td-cat">Enterprise</td><td>Custom</td><td>Per contract</td><td>Per contract</td></tr>
              </tbody>
            </table>
            <p><strong>Automatic renewal.</strong> Pro subscriptions renew automatically. You will receive a reminder email 7 days before each renewal. You may cancel at any time from your Subscription settings page.</p>
            <p><strong>Refunds.</strong> Monthly plans may be refunded within 7 days of the initial purchase if you have not consumed more than 10 AI summaries. Annual plans are non-refundable after 14 days. All refund requests must be submitted to <strong>billing@newsiq.in</strong>.</p>
            <p><strong>Price changes.</strong> We will notify you at least 30 days in advance of any price increase via the email registered to your account. Continued use after the effective date constitutes acceptance of the new price.</p>
            <div className="callout callout-green">
              <span className="callout-icon">✅</span>
              <div className="callout-body"><strong>Students & educators</strong> may apply for a 50% discount at <strong>edu@newsiq.in</strong> with a valid institutional email address.</div>
            </div>
          </div>
        </div>

        {/* Section 6 */}
        <div className="sec" id="tos-6">
          <div className="sec-num"><span>06</span></div>
          <h2 className="sec-title">Acceptable Use Policy</h2>
          <div className="prose">
            <p>You agree to use the Service only for lawful purposes and in ways that do not infringe the rights of others or restrict their use of the Service. The following are expressly prohibited:</p>
            <ul>
              <li>Scraping, crawling, or otherwise automatically extracting content, data, or AI summaries from the Service using bots, scripts, or automated tools.</li>
              <li>Re-publishing, reselling, or commercially redistributing AI summaries or clustered story content without explicit written permission from NewsIQ.</li>
              <li>Circumventing, disabling, or otherwise interfering with security-related features of the Service, including rate limits or access controls.</li>
              <li>Using the Service to spread or amplify demonstrably false information.</li>
              <li>Accessing another user&apos;s account without authorisation.</li>
              <li>Reverse engineering, decompiling, or disassembling any part of the Service or its AI systems.</li>
              <li>Transmitting spam, malware, or any unsolicited commercial communications via Service channels.</li>
              <li>Using the Service in a manner that could damage, overburden, or impair our servers or networks.</li>
            </ul>
            <p>Violation of this policy may result in immediate suspension or termination of your account at our sole discretion, without refund of any prepaid subscription fees.</p>
          </div>
        </div>

        {/* Section 7 */}
        <div className="sec" id="tos-7">
          <div className="sec-num"><span>07</span></div>
          <h2 className="sec-title">Intellectual Property</h2>
          <div className="prose">
            <p><strong>NewsIQ content.</strong> The Service, including but not limited to the AI clustering algorithms, UI design, Signal Bar branding, &quot;NewsIQ&quot; name and logo, Difference Engine methodology, and all original summaries generated by our systems, are the exclusive property of NewsIQ Technologies Private Limited and are protected by applicable copyright, trademark, and other intellectual property laws.</p>
            <p><strong>Third-party content.</strong> All original article text, photographs, and media belong to their respective publishers. NewsIQ claims no ownership over source content. Our AI summaries are transformative works produced under fair dealing principles; however, we do not guarantee that such treatment will be found lawful in every jurisdiction.</p>
            <p><strong>Your content.</strong> By providing any feedback, suggestions, or reports to NewsIQ, you grant us a royalty-free, perpetual, irrevocable licence to use, modify, and incorporate such submissions into the Service without compensation to you.</p>
            <p><strong>Limited licence to you.</strong> NewsIQ grants you a personal, non-exclusive, non-transferable, revocable licence to access and use the Service for your individual, non-commercial news consumption purposes, subject to these Terms.</p>
          </div>
        </div>

        {/* Section 8 */}
        <div className="sec" id="tos-8">
          <div className="sec-num"><span>08</span></div>
          <h2 className="sec-title">Third-Party Content & Links</h2>
          <div className="prose">
            <p>The Service aggregates content from hundreds of third-party publishers, news agencies, and RSS feeds. NewsIQ does not endorse, verify, or take responsibility for the accuracy, completeness, or legality of third-party content.</p>
            <div className="callout callout-amber">
              <span className="callout-icon">⚠️</span>
              <div className="callout-body"><strong>AI summaries may contain inaccuracies.</strong> Our clustering and summarisation systems are not infallible. The Difference Engine is designed to surface contradictions between sources, not to adjudicate which source is correct. Always refer to original sources for critical decisions.</div>
            </div>
            <p>External links in Source Coverage tables open in a new tab and leave the NewsIQ Service. We are not responsible for the content, privacy practices, or terms of third-party websites.</p>
          </div>
        </div>

        {/* Section 9 */}
        <div className="sec" id="tos-9">
          <div className="sec-num"><span>09</span></div>
          <h2 className="sec-title">Disclaimers</h2>
          <div className="prose">
            <p>THE SERVICE IS PROVIDED ON AN &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; BASIS WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, OR NON-INFRINGEMENT.</p>
            <p>We do not warrant that:</p>
            <ul>
              <li>The Service will be uninterrupted, error-free, or free of viruses or other harmful components.</li>
              <li>AI summaries will be accurate, complete, or up-to-date.</li>
              <li>Story clustering will correctly identify all articles relating to a given event.</li>
              <li>The Service will meet your specific requirements.</li>
            </ul>
            <p>NewsIQ is an information aggregation tool, not a news publisher. Nothing on the Service constitutes legal, financial, medical, or professional advice.</p>
          </div>
        </div>

        {/* Section 10 */}
        <div className="sec" id="tos-10">
          <div className="sec-num"><span>10</span></div>
          <h2 className="sec-title">Limitation of Liability</h2>
          <div className="prose">
            <p>TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, NEWSIQ AND ITS DIRECTORS, EMPLOYEES, AGENTS, AND LICENSORS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, GOODWILL, OR OTHER INTANGIBLE LOSSES, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE SERVICE.</p>
            <p>IN NO EVENT SHALL OUR TOTAL LIABILITY TO YOU FOR ALL CLAIMS EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID US IN THE 12 MONTHS PRECEDING THE CLAIM OR (B) ₹500 INR.</p>
            <p>Some jurisdictions do not allow the exclusion or limitation of liability for certain types of damages. In such jurisdictions our liability will be limited to the fullest extent permitted by law.</p>
          </div>
        </div>

        {/* Section 11 */}
        <div className="sec" id="tos-11">
          <div className="sec-num"><span>11</span></div>
          <h2 className="sec-title">Termination</h2>
          <div className="prose">
            <p><strong>By you.</strong> You may terminate your account at any time by visiting Settings → Account → Delete Account. Deletion is permanent. Bookmarks, reading history, and digest preferences will be erased within 30 days of the request.</p>
            <p><strong>By us.</strong> We may suspend or terminate your account, with or without notice, if we reasonably believe you have violated these Terms, if required by law, or if continued provision of the Service to you would expose NewsIQ to legal or reputational harm.</p>
            <p>Upon termination, your licence to use the Service ceases immediately. Sections 7, 9, 10, and 12 survive termination.</p>
          </div>
        </div>

        {/* Section 12 */}
        <div className="sec" id="tos-12">
          <div className="sec-num"><span>12</span></div>
          <h2 className="sec-title">Governing Law & Dispute Resolution</h2>
          <div className="prose">
            <p>These Terms and any dispute arising out of or related to the Service shall be governed by and construed in accordance with the laws of <strong>India</strong>, without regard to its conflict of law provisions.</p>
            <p>You agree to first contact us at <strong>legal@newsiq.in</strong> to attempt informal resolution of any dispute. If a dispute cannot be resolved informally within 30 days, it shall be submitted to binding arbitration in Bengaluru, Karnataka, under the Arbitration and Conciliation Act, 1996.</p>
            <p>Notwithstanding the foregoing, either party may seek emergency injunctive relief from the courts of Bengaluru, Karnataka to protect intellectual property rights or prevent irreparable harm.</p>
          </div>
        </div>

        {/* Section 13 */}
        <div className="sec" id="tos-13">
          <div className="sec-num"><span>13</span></div>
          <h2 className="sec-title">Changes to These Terms</h2>
          <div className="prose">
            <p>We may update these Terms from time to time. When we make material changes, we will:</p>
            <ul>
              <li>Update the &quot;Last updated&quot; date at the top of this page.</li>
              <li>Send an email notification to all registered users at least <strong>14 days before</strong> the changes take effect.</li>
              <li>Display a prominent banner in the app for 30 days following the change.</li>
            </ul>
            <p>Your continued use of the Service after the effective date of revised Terms constitutes your acceptance of those Terms. If you do not agree, you must stop using the Service and may request account deletion.</p>
            <p>All previous versions of the Terms are archived and available upon request at <strong>legal@newsiq.in</strong>.</p>
          </div>
        </div>

        {/* Section 14 */}
        <div className="sec" id="tos-14">
          <div className="sec-num"><span>14</span></div>
          <h2 className="sec-title">Contact Us</h2>
          <div className="prose">
            <p>For any questions, concerns, or legal notices regarding these Terms, please reach out through one of the following channels:</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "16px" }}>
            <div className="contact-chip" onClick={() => toast.info("Opening email client...")}>
              <div className="chip-icon" style={{ background: "rgba(26,86,219,.1)" }}><svg width="15" height="15" style={{ color: "var(--blue)" }}><use href="#i-mail" /></svg></div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Legal Enquiries</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>legal@newsiq.in</div>
              </div>
            </div>
            <div className="contact-chip" onClick={() => toast.info("Opening email client...")}>
              <div className="chip-icon" style={{ background: "rgba(22,163,74,.1)" }}><svg width="15" height="15" style={{ color: "var(--green)" }}><use href="#i-mail" /></svg></div>
              <div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--ink)" }}>Billing & Subscriptions</div>
                <div style={{ fontSize: "12px", color: "var(--ink3)" }}>billing@newsiq.in</div>
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
        </div>

        {/* Footer */}
        <div className="doc-footer">
          <div style={{ fontSize: "13px", color: "var(--ink3)" }}>© 2026 NewsIQ Technologies Private Limited. All rights reserved.</div>
          <div className="doc-footer-nav">
            <Link href="/privacy" className="doc-footer-link">Privacy Policy</Link>
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
          <div className="meta-row"><span className="meta-lbl">Jurisdiction</span><span className="meta-val">India</span></div>
          <div className="meta-row"><span className="meta-lbl">Language</span><span className="meta-val">English</span></div>
        </div>
        <div className="meta-card">
          <div className="meta-card-title">Quick Actions</div>
          <div className="meta-link" onClick={handleDownload}><svg width="13" height="13"><use href="#i-download" /></svg>Download PDF</div>
          <Link href="/privacy" className="meta-link"><svg width="13" height="13"><use href="#i-shield" /></svg>Privacy Policy</Link>
          <div className="meta-link" onClick={handleCopyLink}><svg width="13" height="13"><use href="#i-copy" /></svg>Copy link</div>
        </div>
        <div className="meta-card" style={{ borderColor: "rgba(196,30,58,.2)", background: "rgba(196,30,58,.03)" }}>
          <div className="meta-card-title" style={{ color: "var(--primary)" }}>Need Help?</div>
          <div style={{ fontSize: "13px", color: "var(--ink2)", lineHeight: 1.6, marginBottom: "12px" }}>Questions about these terms? Our team responds within 5 business days.</div>
          <button className="btnp" style={{ width: "100%", justifyContent: "center", fontSize: "13px", padding: "8px 16px" }} onClick={() => toast.info("Opening email client...")}>
            <svg width="13" height="13"><use href="#i-mail" /></svg>Contact legal team
          </button>
        </div>
      </div>
    </div>
  );
}
