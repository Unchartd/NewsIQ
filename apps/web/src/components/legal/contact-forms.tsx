"use client";

import React, { useState } from "react";
import { toast } from "sonner";

export default function ContactForms() {
  const [email, setEmail] = useState("");
  const [inquiryType, setInquiryType] = useState("general");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !subject || !message) {
      toast.error("Please fill in all required fields.");
      return;
    }
    toast.success("Message sent successfully. We will respond within 5 business days.");
    setEmail("");
    setSubject("");
    setMessage("");
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
        <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>Legal Contact Center</h2>
        <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--ink3)" }}>
          Contact our Legal, Privacy, or Publisher relations team.
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
            placeholder="e.g. contact@domain.com"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Inquiry Department *</label>
          <select
            value={inquiryType}
            onChange={(e) => setInquiryType(e.target.value)}
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
            <option value="general">General Legal Inquiries (legal@newsiq.ai)</option>
            <option value="privacy">Privacy / Data Requests (privacy@newsiq.ai)</option>
            <option value="publisher">Publisher Concerns & Opt-Outs</option>
          </select>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Subject *</label>
          <input
            type="text"
            required
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            style={{
              width: "100%",
              padding: "8px 12px",
              borderRadius: "var(--r6)",
              border: "1px solid var(--border)",
              background: "var(--surface)",
              color: "var(--ink)",
              fontSize: "13px"
            }}
            placeholder="Brief summary of your inquiry"
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Message *</label>
          <textarea
            rows={5}
            required
            value={message}
            onChange={(e) => setMessage(e.target.value)}
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
            placeholder="Detailed description of your inquiry or concerns..."
          />
        </div>

        <button
          type="submit"
          className="btnp"
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          Send Message
        </button>
      </form>
    </div>
  );
}
