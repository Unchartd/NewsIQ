"use client";

import React, { useEffect, useState } from "react";
import CookieModal, { CookiePreferences } from "./cookie-modal";

export default function CookieBanner() {
  const [isVisible, setIsVisible] = useState<boolean>(false);
  const [modalOpen, setModalOpen] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const consent = localStorage.getItem("niq_cookie_consent");
      if (!consent) {
        setIsVisible(true);
      }
    }
  }, []);

  const handleAcceptAll = () => {
    const prefs: CookiePreferences = {
      essential: true,
      functional: true,
      analytics: true,
      security: true,
    };
    localStorage.setItem("niq_cookie_consent", JSON.stringify(prefs));
    setIsVisible(false);
  };

  const handleRejectAll = () => {
    const prefs: CookiePreferences = {
      essential: true,
      functional: false,
      analytics: false,
      security: false,
    };
    localStorage.setItem("niq_cookie_consent", JSON.stringify(prefs));
    setIsVisible(false);
  };

  if (!isVisible) {
    return (
      <>
        {/* Render modal if manually opened from footer */}
        <CookieModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
        {/* Global listener to open cookie settings via custom event */}
        <CookieSettingsListener onTrigger={() => setModalOpen(true)} />
      </>
    );
  }

  return (
    <>
      <div style={{
        position: "fixed",
        bottom: "24px",
        left: "24px",
        right: "24px",
        backgroundColor: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r12)",
        boxShadow: "var(--sh3)",
        padding: "20px 24px",
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "24px",
        flexWrap: "wrap"
      }}>
        <div style={{ flex: 1, minWidth: "280px" }}>
          <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--ink)", marginBottom: "4px" }}>
            ✦ Cookie Consent
          </div>
          <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
            We use cookies to verify sessions and measure features. You can accept all, reject non-essential trackers, or customize details in settings. See our{" "}
            <a href="/legal?policy=cookies" style={{ color: "var(--blue)", textDecoration: "underline" }}>Cookie Policy</a>.
          </div>
        </div>
        
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <button 
            onClick={() => setModalOpen(true)}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              color: "var(--ink2)",
              padding: "8px 14px",
              borderRadius: "var(--r6)",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer"
            }}
          >
            Cookie Settings
          </button>
          <button 
            onClick={handleRejectAll}
            style={{
              background: "none",
              border: "1px solid var(--border)",
              color: "var(--ink2)",
              padding: "8px 14px",
              borderRadius: "var(--r6)",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer"
            }}
          >
            Reject Non-Essential
          </button>
          <button 
            onClick={handleAcceptAll}
            className="btnp"
            style={{
              fontSize: "13px",
              padding: "9px 16px"
            }}
          >
            Accept All
          </button>
        </div>
      </div>
      
      <CookieModal 
        isOpen={modalOpen} 
        onClose={() => setModalOpen(false)} 
        onSave={() => setIsVisible(false)} 
      />
    </>
  );
}

// Simple helper component to listen to custom window events to trigger the cookie settings modal
function CookieSettingsListener({ onTrigger }: { onTrigger: () => void }) {
  useEffect(() => {
    const handleTrigger = () => onTrigger();
    window.addEventListener("open-cookie-settings", handleTrigger);
    return () => window.removeEventListener("open-cookie-settings", handleTrigger);
  }, [onTrigger]);
  
  return null;
}
