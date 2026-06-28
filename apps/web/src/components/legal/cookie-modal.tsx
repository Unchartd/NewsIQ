"use client";

import React, { useEffect, useState } from "react";
import { useConsent, ConsentState } from "./consent-provider";
import { toast } from "sonner";

interface CookieModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function CookieModal({ isOpen, onClose }: CookieModalProps) {
  const { 
    essentialEnabled, 
    functionalEnabled, 
    analyticsEnabled, 
    marketingEnabled, 
    region, 
    consentVersion,
    updateConsent 
  } = useConsent();

  // Local state for toggle switches inside the modal
  const [localPrefs, setLocalPrefs] = useState<ConsentState>({
    essential: true,
    functional: false,
    analytics: false,
    marketing: false,
  });

  // Sync local state when modal opens or active preferences load
  useEffect(() => {
    if (isOpen) {
      setLocalPrefs({
        essential: true,
        functional: functionalEnabled,
        analytics: analyticsEnabled,
        marketing: marketingEnabled,
      });
    }
  }, [isOpen, functionalEnabled, analyticsEnabled, marketingEnabled]);

  if (!isOpen) return null;

  const handleToggle = (key: keyof ConsentState) => {
    if (key === "essential") return; // Essential is locked
    setLocalPrefs((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = async () => {
    await updateConsent(localPrefs);
    toast.success("Cookie preferences saved successfully.");
    onClose();
  };

  const handleAcceptAll = async () => {
    const allOn = { essential: true, functional: true, analytics: true, marketing: true };
    setLocalPrefs(allOn);
    await updateConsent(allOn);
    toast.success("Accepted all cookies and third-party trackers.");
    onClose();
  };

  const handleRejectAll = async () => {
    const allOff = { essential: true, functional: false, analytics: false, marketing: false };
    setLocalPrefs(allOff);
    await updateConsent(allOff);
    toast.success("Rejected all non-essential trackers.");
    onClose();
  };

  const handleReset = () => {
    setLocalPrefs({
      essential: true,
      functional: functionalEnabled,
      analytics: analyticsEnabled,
      marketing: marketingEnabled,
    });
    toast.info("Preferences reset to active settings.");
  };

  return (
    <div 
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
        backdropFilter: "blur(6px)",
        animation: "fadeIn 0.2s ease-out",
      }}
    >
      <div 
        style={{
          backgroundColor: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: "16px",
          maxWidth: "600px",
          width: "100%",
          boxShadow: "0 20px 40px -15px rgba(0, 0, 0, 0.3)",
          padding: "28px",
          color: "var(--ink)",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, letterSpacing: "-0.02em" }}>
              Privacy Preference Center
            </h2>
            <div style={{ fontSize: "11px", color: "var(--ink3)", marginTop: "2px" }}>
              Consent Version: {consentVersion} | Region: {region}
            </div>
          </div>
          <button 
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--ink3)",
              fontSize: "18px",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            ✕
          </button>
        </div>

        <p style={{ fontSize: "13px", color: "var(--ink2)", margin: 0, lineHeight: 1.6 }}>
          We use cookies and equivalent browser storage to keep you securely signed in, remember your layout configurations, and analyze platform performance. Customize your compliance settings below.
        </p>

        {/* Categories List */}
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          
          {/* Essential */}
          <div 
            style={{
              padding: "14px",
              background: "var(--surface)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "14px", fontWeight: 600 }}>1. Essential Cookies</span>
                <span style={{ fontSize: "10px", backgroundColor: "var(--border)", padding: "2px 6px", borderRadius: "4px", fontWeight: 500, color: "var(--ink3)" }}>Required</span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
                Strictly necessary for secure authentication, CSRF defense, and email validation cooldown limits.
              </div>
              <div style={{ fontSize: "11px", color: "var(--ink3)", marginTop: "6px" }}>
                <strong>Cookies:</strong> `access_token`, `refresh_token`, `niq_cookie_consent` | <strong>Retention:</strong> 15 mins to 1 year | <strong>Third-party:</strong> No
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <input type="checkbox" checked disabled style={{ width: "18px", height: "18px", accentColor: "var(--blue)" }} />
            </div>
          </div>

          {/* Functional */}
          <div 
            style={{
              padding: "14px",
              background: "var(--surface)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "14px", fontWeight: 600 }}>2. Functional Preferences</span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
                Remembers theme selections (dark/light), sidebar layout modes, and preferred AI summary depth configs.
              </div>
              <div style={{ fontSize: "11px", color: "var(--ink3)", marginTop: "6px" }}>
                <strong>Keys:</strong> `newsiq-ui`, `theme`, `next-themes` | <strong>Retention:</strong> Persistent | <strong>Third-party:</strong> No
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <input 
                type="checkbox" 
                checked={localPrefs.functional}
                onChange={() => handleToggle("functional")}
                style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "var(--blue)" }} 
              />
            </div>
          </div>

          {/* Analytics */}
          <div 
            style={{
              padding: "14px",
              background: "var(--surface)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "14px", fontWeight: 600 }}>3. Performance & Analytics</span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
                Helps us measure site traffic, identify feature usage clickstreams, and optimize response speeds anonymously.
              </div>
              <div style={{ fontSize: "11px", color: "var(--ink3)", marginTop: "6px" }}>
                <strong>Cookies:</strong> `_ga`, `_gid`, `posthog-js` | <strong>Retention:</strong> 24 hrs to 1 year | <strong>Third-party:</strong> Yes (Google, PostHog)
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <input 
                type="checkbox" 
                checked={localPrefs.analytics}
                onChange={() => handleToggle("analytics")}
                style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "var(--blue)" }} 
              />
            </div>
          </div>

          {/* Marketing */}
          <div 
            style={{
              padding: "14px",
              background: "var(--surface)",
              borderRadius: "10px",
              border: "1px solid var(--border)",
              display: "flex",
              justifyContent: "space-between",
              gap: "16px",
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "14px", fontWeight: 600 }}>4. Targeting & Marketing</span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--ink2)", lineHeight: 1.5 }}>
                Tracks campaign success and measures newsletter signup events to serve relevant context on partner channels.
              </div>
              <div style={{ fontSize: "11px", color: "var(--ink3)", marginTop: "6px" }}>
                <strong>Cookies:</strong> `_fbp`, `LinkedIn Insight` | <strong>Retention:</strong> 30 to 90 days | <strong>Third-party:</strong> Yes (Meta, LinkedIn)
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center" }}>
              <input 
                type="checkbox" 
                checked={localPrefs.marketing}
                onChange={() => handleToggle("marketing")}
                style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "var(--blue)" }} 
              />
            </div>
          </div>

        </div>

        {/* Footer Actions */}
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", marginTop: "10px" }}>
          <div>
            <button 
              onClick={handleReset}
              style={{
                background: "none",
                border: "none",
                color: "var(--ink2)",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
                padding: "8px 0",
                textDecoration: "underline",
              }}
            >
              Reset Settings
            </button>
          </div>
          
          <div style={{ display: "flex", gap: "10px" }}>
            <button 
              onClick={handleAcceptAll}
              style={{
                background: "none",
                border: "1px solid var(--border)",
                color: "var(--ink)",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Accept All
            </button>

            <button 
              onClick={handleSave}
              className="btnp"
              style={{
                fontSize: "13px",
                padding: "9px 18px",
                borderRadius: "8px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Save Preferences
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
