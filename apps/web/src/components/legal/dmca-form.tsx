"use client";

import React, { useState } from "react";
import { toast } from "sonner";

export default function DmcaForm() {
  const [formType, setFormType] = useState<"takedown" | "counter">("takedown");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [description, setDescription] = useState("");
  const [signature, setSignature] = useState("");
  const [declaration, setDeclaration] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !email || !targetUrl || !signature || !declaration) {
      toast.error("Please fill in all required fields and accept the legal declaration.");
      return;
    }
    toast.success("Request submitted successfully. Our legal department will review within 72 hours.");
    // Clear form
    setName("");
    setEmail("");
    setTargetUrl("");
    setDescription("");
    setSignature("");
    setDeclaration(false);
  };

  return (
    <div style={{
      backgroundColor: "var(--card)",
      border: "1px solid var(--border)",
      borderRadius: "var(--r12)",
      padding: "24px",
      color: "var(--ink)",
      display: "flex",
      flexDirection: "column",
      gap: "20px"
    }}>
      <div>
        <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>DMCA / Intellectual Property Center</h2>
        <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--ink3)" }}>
          Submit a Copyright Takedown Request or Counter-Notice to the NewsIQ Legal team.
        </p>
      </div>

      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border)", paddingBottom: "12px" }}>
        <button
          onClick={() => setFormType("takedown")}
          className={formType === "takedown" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Submit Takedown Notice
        </button>
        <button
          onClick={() => setFormType("counter")}
          className={formType === "counter" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Submit Counter-Notice
        </button>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: "200px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Full Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--r6)",
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "13px"
              }}
              placeholder="Legal name of rights holder"
            />
          </div>
          <div style={{ flex: 1, minWidth: "200px" }}>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Contact Email *</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "var(--r6)",
                border: "1px solid var(--border)",
                background: "var(--surface)",
                color: "var(--ink)",
                fontSize: "13px"
              }}
              placeholder="e.g. copyright@publisher.com"
            />
          </div>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
            {formType === "takedown" ? "URL of Infringing Material on NewsIQ *" : "URL of Removed Material *"}
          </label>
          <input
            type="url"
            required
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--r6)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--ink)",
              fontSize: "13px"
            }}
            placeholder="https://newsiq.ai/story/..."
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>
            {formType === "takedown" ? "Describe copyrighted work and evidence of infringement" : "Rationale for restoration"}
          </label>
          <textarea
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--r6)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--ink)",
              fontSize: "13px",
              resize: "vertical"
            }}
            placeholder={formType === "takedown" ? "Details, publisher name, or trademark identifiers..." : "Reasons why removal was a mistake..."}
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Digital Signature *</label>
          <input
            type="text"
            required
            value={signature}
            onChange={(e) => setSignature(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--r6)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--ink)",
              fontSize: "13px",
              fontFamily: "monospace"
            }}
            placeholder="/s/ Firstname Lastname"
          />
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "flex-start", marginTop: "4px" }}>
          <input
            type="checkbox"
            required
            checked={declaration}
            onChange={(e) => setDeclaration(e.target.checked)}
            style={{ marginTop: "3px", cursor: "pointer" }}
            id="dmca-decl"
          />
          <label htmlFor="dmca-decl" style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5, cursor: "pointer" }}>
            {formType === "takedown" ? (
              <>
                <strong>I declare under penalty of perjury</strong> that I am the authorized copyright holder or representative, and the information in this notice is accurate and complete.
              </>
            ) : (
              <>
                <strong>I declare under penalty of perjury</strong> that I have a good-faith belief that the material was removed or disabled as a result of mistake or misidentification.
              </>
            )}

          </label>
        </div>

        <button
          type="submit"
          className="btnp"
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          {formType === "takedown" ? "Submit Takedown notice" : "Submit Counter-Notice"}
        </button>
      </form>
    </div>
  );
}
