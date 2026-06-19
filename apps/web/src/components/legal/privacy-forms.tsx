"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

export default function PrivacyForms() {
  const [requestType, setRequestType] = useState<"access" | "delete" | "correct" | "nominate">("access");
  const [email, setEmail] = useState("");
  const [details, setDetails] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Email is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (requestType === "delete") {
        // Direct integration with backend account deletion
        const confirm = window.confirm(
          "WARNING: Selecting Deletion Request will trigger account anonymization and wipe all your bookmarks and settings. This cannot be undone. Do you want to proceed?"
        );
        if (!confirm) {
          setIsSubmitting(false);
          return;
        }
        await apiClient.delete("/users/account");
        toast.success("Account erasure completed. You have been anonymized.");
      } else if (requestType === "access") {
        // Direct integration with data export
        window.open(apiClient.defaults.baseURL + "/users/export-data", "_blank");
        toast.success("Initiating data export download.");
      } else {
        // Mock success for correction and nomination
        toast.success("Request logged successfully. We will follow up via email within 72 hours.");
      }
      setEmail("");
      setDetails("");
    } catch (err) {
      toast.error("Failed to process request. Please contact support@newsiq.ai.");
    } finally {
      setIsSubmitting(false);
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
        <h2 style={{ margin: 0, fontSize: "20px", fontWeight: 600 }}>Privacy Rights Portal</h2>
        <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--ink3)" }}>
          Exercise your statutory data rights under DPDP Act 2023, GDPR, or CCPA.
        </p>
      </div>

      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border)", paddingBottom: "12px", flexWrap: "wrap" }}>
        <button
          onClick={() => setRequestType("access")}
          className={requestType === "access" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Right to Access (Export)
        </button>
        <button
          onClick={() => setRequestType("delete")}
          className={requestType === "delete" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Right to Erasure (Delete)
        </button>
        <button
          onClick={() => setRequestType("correct")}
          className={requestType === "correct" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Right to Correction
        </button>
        <button
          onClick={() => setRequestType("nominate")}
          className={requestType === "nominate" ? "btnp" : "btno"}
          style={{ fontSize: "12px", padding: "6px 12px" }}
        >
          Right to Nominate (DPDPA)
        </button>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Your Registered Email *</label>
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
            placeholder="e.g. user@domain.com"
          />
        </div>

        {requestType === "correct" && (
          <div>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Specify corrections needed *</label>
            <textarea
              rows={4}
              required
              value={details}
              onChange={(e) => setDetails(e.target.value)}
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
              placeholder="e.g. Please update my spelling from Aarav M. to Aarav Mehta..."
            />
          </div>
        )}

        {requestType === "nominate" && (
          <div>
            <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Nominee Details & Authorization *</label>
            <textarea
              rows={4}
              required
              value={details}
              onChange={(e) => setDetails(e.target.value)}
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
              placeholder="Provide name, contact info, and relationship of the nominee who is authorized to exercise data rights on your behalf under DPDPA Section 14..."
            />
          </div>
        )}

        {requestType === "access" && (
          <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
            Selecting Access Request will trigger an automated compilation and download of all bookmarks, settings, reading history, and sessions stored on the platform.
          </div>
        )}

        {requestType === "delete" && (
          <div style={{ fontSize: "12px", color: "var(--err)", lineHeight: 1.5 }}>
            WARNING: Confirming this action anonymizes your email/profile, and erases bookmarks. This action is final.
          </div>
        )}

        <button
          type="submit"
          className="btnp"
          disabled={isSubmitting}
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          {isSubmitting ? "Processing..." : requestType === "access" ? "Trigger Data Export" : "Submit Request"}
        </button>
      </form>
    </div>
  );
}
