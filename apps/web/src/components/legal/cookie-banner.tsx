"use client";

import React, { useState } from "react";
import CookieModal from "./cookie-modal";
import { useConsent } from "./consent-provider";

export default function CookieBanner() {
  const { showBanner, setShowBanner, updateConsent, loading, region } = useConsent();
  const [modalOpen, setModalOpen] = useState<boolean>(false);

  if (loading || !showBanner) {
    return (
      <>
        <CookieModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
        <CookieSettingsListener onTrigger={() => setModalOpen(true)} />
      </>
    );
  }

  const handleAcceptAll = async () => {
    await updateConsent({
      essential: true,
      functional: true,
      analytics: true,
      marketing: true,
    });
  };

  const handleRejectAll = async () => {
    await updateConsent({
      essential: true,
      functional: false,
      analytics: false,
      marketing: false,
    });
  };

  return (
    <>
      <div 
        style={{
          position: "fixed",
          bottom: "24px",
          left: "24px",
          right: "24px",
          backgroundColor: "rgba(var(--card-rgb, 255, 255, 255), 0.85)",
          border: "1px solid var(--border)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.15)",
          padding: "24px",
          zIndex: 9999,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "24px",
          flexWrap: "wrap",
          backdropFilter: "blur(12px)",
          transition: "all 0.3s ease-in-out",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <div style={{ flex: 1, minWidth: "280px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <span style={{ fontSize: "16px" }}>🔒</span>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--ink)" }}>
              Cookie & Privacy Preferences ({region === "CA" ? "US / CA Rights" : region})
            </div>
          </div>
          <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.6 }}>
            NewsIQ uses cookies to secure session authentication and maintain layout state. Depending on your region, we may also request permission to run privacy-focused analytics and marketing pixels. Read our{" "}
            <a href="/legal?policy=cookies" style={{ color: "var(--blue)", textDecoration: "underline", fontWeight: 500 }}>
              Cookie Policy
            </a>{" "}
            to learn more.
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
          <button 
            onClick={() => setModalOpen(true)}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              color: "var(--ink)",
              padding: "10px 18px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--surface)")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          >
            Customize
          </button>
          
          <button 
            onClick={handleRejectAll}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              color: "var(--ink2)",
              padding: "10px 18px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background 0.2s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--surface)")}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
          >
            Reject Non-Essential
          </button>

          <button 
            onClick={handleAcceptAll}
            className="btnp"
            style={{
              fontSize: "13px",
              padding: "11px 20px",
              borderRadius: "8px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Accept All
          </button>
        </div>
      </div>

      <CookieModal 
        isOpen={modalOpen} 
        onClose={() => setModalOpen(false)} 
      />
    </>
  );
}

function CookieSettingsListener({ onTrigger }: { onTrigger: () => void }) {
  React.useEffect(() => {
    const handleTrigger = () => onTrigger();
    window.addEventListener("open-cookie-settings", handleTrigger);
    return () => window.removeEventListener("open-cookie-settings", handleTrigger);
  }, [onTrigger]);
  
  return null;
}
