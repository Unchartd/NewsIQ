"use client";

import React, { Suspense, useEffect, useState, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { normalizedPolicies, PolicyDocument, PolicySection } from "../normalized-content";

// Import compliance forms
import PrivacyForms from "@/components/legal/privacy-forms";
import DmcaForm from "@/components/legal/dmca-form";
import AbuseForm from "@/components/legal/abuse-form";
import ContactForms from "@/components/legal/contact-forms";

// Component that reads search params and renders the legal center
function LegalPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const policyParam = searchParams.get("policy");

  const [activePolicyKey, setActivePolicyKey] = useState<string>("tos");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [activeAnchor, setActiveAnchor] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);

  // Set active policy based on query param
  useEffect(() => {
    if (policyParam) {
      setActivePolicyKey(policyParam);
    }
  }, [policyParam]);

  const activePolicy = useMemo<PolicyDocument | null>(() => {
    return normalizedPolicies[activePolicyKey] || null;
  }, [activePolicyKey]);

  // Filter sections by search query
  const filteredSections = useMemo<PolicySection[]>(() => {
    if (!activePolicy) return [];
    if (!searchQuery.trim()) return activePolicy.sections;
    const query = searchQuery.toLowerCase();
    return activePolicy.sections.filter(
      (sec) =>
        sec.title.toLowerCase().includes(query) ||
        sec.content.toLowerCase().includes(query)
    );
  }, [activePolicy, searchQuery]);

  // Set up scroll observer to highlight active TOC item
  useEffect(() => {
    if (!activePolicy) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            setActiveAnchor(e.target.id);
          }
        });
      },
      { rootMargin: "-20% 0px -60% 0px", threshold: 0 }
    );

    const sections = document.querySelectorAll(".sec");
    sections.forEach((s) => observer.observe(s));

    return () => observer.disconnect();
  }, [activePolicyKey, filteredSections, activePolicy]);

  const handlePolicyChange = (key: string) => {
    setSearchQuery("");
    setActiveAnchor("");
    setMobileMenuOpen(false);
    router.push(`/legal?policy=${key}`);
  };

  const handleDownload = () => {
    if (activePolicy) {
      toast.success(`Downloading ${activePolicy.title} PDF...`);
    } else {
      toast.success("Downloading forms PDF...");
    }
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success("Link copied to clipboard");
  };

  const isFormSelected = ["privacy-form", "dmca-form", "abuse-form", "contact-form"].includes(activePolicyKey);

  return (
    <div className="legal-layout">
      {/* Mobile Drawer Trigger */}
      <button 
        className="mobile-toc-toggle"
        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
      >
        {mobileMenuOpen ? "✕ Close Navigation" : "☰ Browse Policies & Forms"}
      </button>

      {/* ── LEFT SIDEBAR (Policy Selector) ── */}
      <nav className={`toc-col ${mobileMenuOpen ? "mobile-open" : ""}`}>
        <div className="toc-header">Legal Policies</div>
        <ul className="toc-list">
          {Object.entries(normalizedPolicies).map(([key, doc]) => (
            <li key={key}>
              <button
                className={`toc-item ${activePolicyKey === key ? "active" : ""}`}
                onClick={() => handlePolicyChange(key)}
                style={{ width: "100%", textAlign: "left", background: "none", border: "none" }}
              >
                <span className="toc-num">●</span>
                {doc.title}
              </button>
            </li>
          ))}
        </ul>
        <div className="toc-divider"></div>
        <div className="toc-header">Compliance Forms</div>
        <ul className="toc-list">
          <li>
            <button
              className={`toc-item ${activePolicyKey === "privacy-form" ? "active" : ""}`}
              onClick={() => handlePolicyChange("privacy-form")}
              style={{ width: "100%", textAlign: "left", background: "none", border: "none" }}
            >
              <span className="toc-num">✦</span>
              Privacy Rights Portal
            </button>
          </li>
          <li>
            <button
              className={`toc-item ${activePolicyKey === "dmca-form" ? "active" : ""}`}
              onClick={() => handlePolicyChange("dmca-form")}
              style={{ width: "100%", textAlign: "left", background: "none", border: "none" }}
            >
              <span className="toc-num">✦</span>
              DMCA Takedown Center
            </button>
          </li>
          <li>
            <button
              className={`toc-item ${activePolicyKey === "abuse-form" ? "active" : ""}`}
              onClick={() => handlePolicyChange("abuse-form")}
              style={{ width: "100%", textAlign: "left", background: "none", border: "none" }}
            >
              <span className="toc-num">✦</span>
              Report Platform Abuse
            </button>
          </li>
          <li>
            <button
              className={`toc-item ${activePolicyKey === "contact-form" ? "active" : ""}`}
              onClick={() => handlePolicyChange("contact-form")}
              style={{ width: "100%", textAlign: "left", background: "none", border: "none" }}
            >
              <span className="toc-num">✦</span>
              Contact Legal/Grievance
            </button>
          </li>
        </ul>
        <div className="toc-divider"></div>
        <div style={{ padding: "0 10px", fontSize: "11px", color: "var(--ink3)" }}>
          Effective: June 15, 2026
        </div>
      </nav>

      {/* ── MAIN CONTENT ── */}
      <div className="doc-col">
        {/* Search Header (Only show when viewing policy documents) */}
        {!isFormSelected && activePolicy && (
          <div className="legal-search-container" style={{ marginBottom: "24px" }}>
            <input
              type="text"
              className="legal-search-input"
              placeholder={`Search in ${activePolicy.title}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 14px",
                borderRadius: "var(--r8)",
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "14px",
              }}
            />
          </div>
        )}

        {/* Dynamic Section rendering */}
        {activePolicyKey === "privacy-form" ? (
          <PrivacyForms />
        ) : activePolicyKey === "dmca-form" ? (
          <DmcaForm />
        ) : activePolicyKey === "abuse-form" ? (
          <AbuseForm />
        ) : activePolicyKey === "contact-form" ? (
          <ContactForms />
        ) : activePolicy ? (
          /* Normal Policy Content */
          <>
            {/* Hero */}
            <div className="doc-hero">
              <div className="doc-eyebrow">
                <svg width="14" height="14"><use href="#i-shield" /></svg>NewsIQ Legal
              </div>
              <h1 className="doc-title">{activePolicy.title}</h1>
              <p className="doc-subtitle">{activePolicy.subtitle}</p>
              <div className="doc-meta-pills">
                <span className="doc-pill">📅 Effective: {activePolicy.effectiveDate}</span>
                <span className="doc-pill ver-badge">Version {activePolicy.version}</span>
                {activePolicy.lawContext && (
                  <span className="doc-pill" style={{ color: "var(--primary)", background: "rgba(196, 30, 58, 0.05)" }}>
                    ⚖️ {activePolicy.lawContext}
                  </span>
                )}
                <button
                  className="doc-pill"
                  style={{ cursor: "pointer", border: "1px solid var(--border)", background: "var(--surface)" }}
                  onClick={handleDownload}
                >
                  <svg width="11" height="11"><use href="#i-download" /></svg>Download PDF
                </button>
              </div>
            </div>

            {/* Policy Sections */}
            {filteredSections.length > 0 ? (
              filteredSections.map((sec, idx) => (
                <div className="sec" id={sec.id} key={sec.id}>
                  <div className="sec-num">
                    <span>{String(idx + 1).padStart(2, "0")}</span>
                  </div>
                  <h2 className="sec-title">{sec.title}</h2>
                  <div className="prose">
                    <p>{sec.content}</p>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ padding: "40px 0", textAlign: "center", color: "var(--ink3)" }}>
                No sections match your search query.
              </div>
            )}

            {/* Dynamic Cookie Inventory Table for Phase 11 */}
            {activePolicyKey === "cookies" && (
              <div className="sec" id="cookie-table" style={{ marginTop: "40px" }}>
                <h2 className="sec-title" style={{ marginBottom: "16px" }}>Cookie & Browser Storage Inventory</h2>
                <div style={{ overflowX: "auto", border: "1px solid var(--border)", borderRadius: "var(--r8)", background: "var(--surface)", boxShadow: "var(--sh1)" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                    <thead>
                      <tr style={{ borderBottom: "2px solid var(--border)", background: "var(--surface)", opacity: 0.85 }}>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Cookie Name / Key</th>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Purpose</th>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Category</th>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Retention</th>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Third Party</th>
                        <th style={{ padding: "12px 14px", fontWeight: 600 }}>Consent</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { name: "access_token", purpose: "JWT user authentication session", cat: "Essential", ret: "15 mins", tp: "No", consent: "No" },
                        { name: "refresh_token", purpose: "Rotating refresh token for new access JWTs", cat: "Essential", ret: "30 days", tp: "No", consent: "No" },
                        { name: "niq_cookie_consent", purpose: "Stores granular cookie choice preferences", cat: "Essential", ret: "1 year", tp: "No", consent: "No" },
                        { name: "resend_cooldown", purpose: "Blocks spamming verification link requests", cat: "Essential", ret: "60 secs", tp: "No", consent: "No" },
                        { name: "newsiq-auth", purpose: "Persists visual profile parameters", cat: "Essential", ret: "Persistent", tp: "No", consent: "No" },
                        { name: "newsiq-ui", purpose: "UI settings (sidebar, AI summary depth)", cat: "Functional", ret: "Persistent", tp: "No", consent: "Yes" },
                        { name: "theme / next-themes", purpose: "Remembers dark/light mode configurations", cat: "Functional", ret: "Persistent", tp: "No", consent: "Yes" },
                        { name: "_ga / _gid", purpose: "Traffic and engagement metrics (Google)", cat: "Analytics", ret: "24h - 2yrs", tp: "Yes", consent: "Yes" },
                        { name: "ph_*_user", purpose: "Feature clickstream telemetry (PostHog)", cat: "Analytics", ret: "1 year", tp: "Yes", consent: "Yes" },
                        { name: "_fbp", purpose: "Facebook ad campaign conversion metrics", cat: "Marketing", ret: "90 days", tp: "Yes", consent: "Yes" },
                        { name: "LinkedIn Insight", purpose: "LinkedIn professional campaign tracking", cat: "Marketing", ret: "30 days", tp: "Yes", consent: "Yes" }
                      ].map((row, index) => (
                        <tr key={index} style={{ borderBottom: "1px solid var(--border)", transition: "background .15s" }}>
                          <td style={{ padding: "12px 14px", fontFamily: "monospace", color: "var(--blue)", fontWeight: 600 }}>{row.name}</td>
                          <td style={{ padding: "12px 14px", color: "var(--ink)" }}>{row.purpose}</td>
                          <td style={{ padding: "12px 14px", color: "var(--ink2)" }}>{row.cat}</td>
                          <td style={{ padding: "12px 14px", color: "var(--ink3)" }}>{row.ret}</td>
                          <td style={{ padding: "12px 14px", color: "var(--ink3)" }}>{row.tp}</td>
                          <td style={{ padding: "12px 14px", fontWeight: row.consent === "Yes" ? 600 : 400, color: row.consent === "Yes" ? "var(--amber)" : "var(--ink3)" }}>
                            {row.consent === "Yes" ? "Consent Required" : "Strictly Necessary"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ padding: "80px", textAlign: "center", color: "var(--ink3)" }}>
            Select a document or form from the sidebar.
          </div>
        )}

        {/* Consent Callout */}
        {activePolicyKey === "privacy" && (
          <div className="callout callout-green" style={{ marginTop: "32px" }}>
            <span className="callout-icon">🛡️</span>
            <div className="callout-body">
              <strong>Your Privacy Control:</strong> NewsIQ is an ad-free service. We never sell your personal information. You can exercise your right to access, export, or erase your account details under the settings tab.
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="doc-footer">
          <div style={{ fontSize: "13px", color: "var(--ink3)" }}>
            © 2026 NewsIQ Technologies Private Limited. All rights reserved.
          </div>
          <div className="doc-footer-nav">
            <button
              onClick={() => handlePolicyChange("tos")}
              style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", fontSize: "13px" }}
            >
              Terms of Service
            </button>
            <span style={{ color: "var(--border)" }}>|</span>
            <button
              onClick={() => handlePolicyChange("privacy")}
              style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", fontSize: "13px" }}
            >
              Privacy Policy
            </button>
          </div>
        </div>
      </div>

      {/* ── RIGHT COLUMN (TOC Anchors) ── */}
      <div className="meta-col">
        {!isFormSelected && activePolicy ? (
          <>
            <div className="meta-card">
              <div className="meta-card-title">Sections</div>
              <div className="toc-sublist" style={{ maxHeight: "300px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "4px" }}>
                {filteredSections.map((sec, idx) => (
                  <a
                    href={`#${sec.id}`}
                    key={sec.id}
                    className={`toc-anchor-link ${activeAnchor === sec.id ? "active" : ""}`}
                    style={{
                      fontSize: "12px",
                      textDecoration: "none",
                      color: activeAnchor === sec.id ? "var(--primary)" : "var(--ink3)",
                      fontWeight: activeAnchor === sec.id ? 600 : 400,
                      padding: "4px 0",
                      display: "block",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis"
                    }}
                  >
                    <span style={{ marginRight: "6px", fontSize: "10px", opacity: 0.7 }}>
                      {String(idx + 1).padStart(2, "0")}
                    </span>
                    {sec.title}
                  </a>
                ))}
              </div>
            </div>

            <div className="meta-card">
              <div className="meta-card-title">Actions</div>
              <div className="meta-link" onClick={handleDownload} style={{ cursor: "pointer" }}>
                <svg width="13" height="13"><use href="#i-download" /></svg>Download PDF
              </div>
              <div className="meta-link" onClick={handleCopyLink} style={{ cursor: "pointer" }}>
                <svg width="13" height="13"><use href="#i-copy" /></svg>Copy Link
              </div>
            </div>
          </>
        ) : (
          <div className="meta-card">
            <div className="meta-card-title">Action Center</div>
            <div style={{ fontSize: "12.5px", color: "var(--ink2)", lineHeight: 1.5 }}>
              Use these interactive portals to submit legal requests directly to the compliance department. Submissions generate automated tickets.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function LegalPage() {
  return (
    <Suspense fallback={<div style={{ padding: "80px", textAlign: "center", color: "var(--ink3)" }}>Loading legal center...</div>}>
      <LegalPageContent />
    </Suspense>
  );
}
