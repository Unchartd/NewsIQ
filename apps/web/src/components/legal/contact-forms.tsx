"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import { Honeypot } from "@/components/legal/honeypot";
import { legalRequestErrorMessage, submitLegalRequest } from "@/lib/legal-requests";


export default function ContactForms() {
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [sending, setSending] = useState(false);
  const [inquiryType, setInquiryType] = useState("general");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !subject || !message) {
      toast.error("Please fill in all required fields.");
      return;
    }
    // This used to say "Message sent" and send nothing.
    setSending(true);
    try {
      const reference = await submitLegalRequest({
        kind: "contact",
        request_type: inquiryType,
        email,
        subject,
        details: message,
        website,
      });
      toast.success(`Message sent (reference ${reference}). We will reply to ${email}.`);
      setEmail("");
      setSubject("");
      setMessage("");
    } catch (err) {
      toast.error(legalRequestErrorMessage(err));
    } finally {
      setSending(false);
    }
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
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }} htmlFor="your-email-address">Your Email Address *</label>
          <input
              id="your-email-address"
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
            <option value="general">General or legal enquiry</option>
            <option value="privacy">Privacy or data request</option>
            <option value="publisher">Publisher Concerns & Opt-Outs</option>
          </select>
        </div>

        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }} htmlFor="subject">Subject *</label>
          <input
              id="subject"
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
          disabled={sending}
          className="btnp"
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          Send Message
        </button>
      <Honeypot value={website} onChange={setWebsite} />
      </form>
    </div>
  );
}
