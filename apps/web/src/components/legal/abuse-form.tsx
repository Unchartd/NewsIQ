"use client";

import React, { useState } from "react";
import { toast } from "sonner";

export default function AbuseForm() {
  const [email, setEmail] = useState("");
  const [category, setCategory] = useState("scraping");
  const [description, setDescription] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !description) {
      toast.error("Please fill in all required fields.");
      return;
    }
    toast.success("Abuse report submitted. Our security operations team will investigate immediately.");
    setEmail("");
    setDescription("");
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
        <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>Report Abuse Center</h2>
        <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--ink3)" }}>
          Report violations of our Acceptable Use Policy.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Your Email Address *</label>
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
            placeholder="e.g. reporter@domain.com"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Abuse Category *</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--r6)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--ink)",
              fontSize: "13px",
              cursor: "pointer"
            }}
          >
            <option value="scraping">Unauthorized Crawling / Scraping</option>
            <option value="credentials">Credential Sharing / Subscription Abuse</option>
            <option value="security">Security Vulnerability / Port Probing</option>
            <option value="malware">Malware / Phishing Campaign</option>
            <option value="ai">AI Feature Misuse (Misinformation / Disinformation)</option>
          </select>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Description of Incident *</label>
          <textarea
            rows={5}
            required
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
            placeholder="Please provide details, timestamps, IP addresses (if known), or links demonstrating AUP violations..."
          />
        </div>

        <button
          type="submit"
          className="btnp"
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          Submit Abuse Report
        </button>
      </form>
    </div>
  );
}
