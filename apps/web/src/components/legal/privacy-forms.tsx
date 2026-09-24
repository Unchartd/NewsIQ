"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { legalRequestErrorMessage, submitLegalRequest } from "@/lib/legal-requests";
import { useAuthStore } from "@/stores/auth-store";

export default function PrivacyForms() {
  const [requestType, setRequestType] = useState<"access" | "delete" | "correct" | "nominate">("access");
  const [email, setEmail] = useState("");
  const [details, setDetails] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [website, setWebsite] = useState(""); // honeypot
  const { isAuthenticated } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Email is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (requestType === "delete" && isAuthenticated) {
        // Signed in: erase immediately.
        const confirm = window.confirm(
          "This anonymises your account and deletes your bookmarks, history and settings. It cannot be undone. Continue?"
        );
        if (!confirm) {
          setIsSubmitting(false);
          return;
        }
        await apiClient.delete("/users/account");
        toast.success("Your account has been deleted and your personal data erased.");
      } else if (requestType === "access" && isAuthenticated) {
        // Signed in: download immediately.
        window.open(apiClient.defaults.baseURL + "/users/export-data", "_blank");
        toast.success("Your data export is downloading.");
      } else {
        // Correction, nomination, or a request made while signed out: this
        // used to show "Request logged" and send nothing. It is now emailed
        // to the monitored inbox and handled by hand, with identity checked
        // by email before any data is released or erased.
        const reference = await submitLegalRequest({
          kind: "privacy",
          email,
          request_type: requestType,
          subject: `Privacy request: ${requestType}`,
          details: details.trim() || `Please process my ${requestType} request for the account ${email}.`,
          website,
        });
        toast.success(`Request sent (reference ${reference}). We will reply to ${email} within 30 days.`);
      }
      setEmail("");
      setDetails("");
    } catch (err) {
      toast.error(legalRequestErrorMessage(err));
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
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }} htmlFor="your-registered-email">Your Registered Email *</label>
          <input
              id="your-registered-email"
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
              placeholder="e.g. Please correct the name on my account to ..."
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
            {isAuthenticated
              ? "Downloads a file with your profile, preferences, bookmarks, notifications and reading history."
              : "Sign in to download your data instantly, or send this request and we will verify your identity by email first."}
          </div>
        )}

        {requestType === "delete" && (
          <div style={{ fontSize: "12px", color: "var(--err)", lineHeight: 1.5 }}>
            {isAuthenticated
              ? "This anonymises your account and erases your bookmarks, history and settings. It cannot be undone."
              : "Sign in to delete your account instantly, or send this request and we will verify your identity by email first."}
          </div>
        )}

        <input
          type="text"
          name="website"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          style={{ position: "absolute", left: "-10000px", width: 1, height: 1, opacity: 0 }}
        />

        <button
          type="submit"
          className="btnp"
          disabled={isSubmitting}
          style={{ width: "100%", justifyContent: "center", padding: "10px 18px", marginTop: "8px" }}
        >
          {isSubmitting ? "Sending..." : requestType === "access" && isAuthenticated ? "Download my data" : "Submit request"}
        </button>
      </form>
    </div>
  );
}
