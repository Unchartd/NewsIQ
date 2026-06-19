"use client";

import React, { useEffect, useState } from "react";
import { toast } from "sonner";

export interface CookiePreferences {
  essential: boolean;
  functional: boolean;
  analytics: boolean;
  security: boolean;
}

interface CookieModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave?: (prefs: CookiePreferences) => void;
}

export default function CookieModal({ isOpen, onClose, onSave }: CookieModalProps) {
  const [prefs, setPrefs] = useState<CookiePreferences>({
    essential: true,
    functional: true,
    analytics: true,
    security: true,
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("niq_cookie_consent");
      if (stored) {
        try {
          setPrefs(JSON.parse(stored));
        } catch (e) {
          // ignore
        }
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleToggle = (key: keyof CookiePreferences) => {
    if (key === "essential") return; // cannot toggle essential
    setPrefs((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = () => {
    localStorage.setItem("niq_cookie_consent", JSON.stringify(prefs));
    if (onSave) onSave(prefs);
    toast.success("Cookie preferences saved successfully.");
    onClose();
  };

  const handleAcceptAll = () => {
    const allOn = { essential: true, functional: true, analytics: true, security: true };
    localStorage.setItem("niq_cookie_consent", JSON.stringify(allOn));
    if (onSave) onSave(allOn);
    toast.success("Accepted all cookies.");
    onClose();
  };

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: "rgba(0, 0, 0, 0.5)",
      zIndex: 10000,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "16px",
      backdropFilter: "blur(4px)"
    }}>
      <div style={{
        backgroundColor: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r12)",
        maxWidth: "500px",
        width: "100%",
        boxShadow: "var(--sh3)",
        padding: "24px",
        color: "var(--ink)",
        display: "flex",
        flexDirection: "column",
        gap: "16px"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600 }}>Cookie Preference Settings</h2>
          <button 
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--ink3)",
              fontSize: "20px",
              cursor: "pointer"
            }}
          >
            ✕
          </button>
        </div>
        
        <p style={{ fontSize: "13px", color: "var(--ink3)", margin: 0, lineHeight: 1.5 }}>
          NewsIQ uses cookies to enhance platform stability, remember configuration settings, and measure feature usage. Customize your choices below.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {/* Essential */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px",
            background: "var(--surface)",
            borderRadius: "var(--r8)",
            border: "1px solid var(--border)"
          }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 600 }}>Essential Cookies</div>
              <div style={{ fontSize: "12px", color: "var(--ink3)" }}>Required for user login sessions and safety mechanisms.</div>
            </div>
            <input type="checkbox" checked disabled style={{ width: "16px", height: "16px" }} />
          </div>

          {/* Functional */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px",
            background: "var(--surface)",
            borderRadius: "var(--r8)",
            border: "1px solid var(--border)"
          }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 600 }}>Functional Cookies</div>
              <div style={{ fontSize: "12px", color: "var(--ink3)" }}>Remembers layout details, summary depths, and dark/light themes.</div>
            </div>
            <input 
              type="checkbox" 
              checked={prefs.functional}
              onChange={() => handleToggle("functional")}
              style={{ width: "16px", height: "16px", cursor: "pointer" }} 
            />
          </div>

          {/* Analytics */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px",
            background: "var(--surface)",
            borderRadius: "var(--r8)",
            border: "1px solid var(--border)"
          }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 600 }}>Analytics Cookies</div>
              <div style={{ fontSize: "12px", color: "var(--ink3)" }}>Anonymously registers click streams, scroll rates, and features used.</div>
            </div>
            <input 
              type="checkbox" 
              checked={prefs.analytics}
              onChange={() => handleToggle("analytics")}
              style={{ width: "16px", height: "16px", cursor: "pointer" }} 
            />
          </div>

          {/* Security */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "12px",
            background: "var(--surface)",
            borderRadius: "var(--r8)",
            border: "1px solid var(--border)"
          }}>
            <div>
              <div style={{ fontSize: "14px", fontWeight: 600 }}>Security Cookies</div>
              <div style={{ fontSize: "12px", color: "var(--ink3)" }}>Monitors access rates to block scraper bots and secure active credentials.</div>
            </div>
            <input 
              type="checkbox" 
              checked={prefs.security}
              onChange={() => handleToggle("security")}
              style={{ width: "16px", height: "16px", cursor: "pointer" }} 
            />
          </div>
        </div>

        <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end", marginTop: "8px" }}>
          <button className="btno" onClick={handleAcceptAll} style={{ fontSize: "13px", padding: "8px 16px" }}>
            Accept All
          </button>
          <button className="btnp" onClick={handleSave} style={{ fontSize: "13px", padding: "8px 16px" }}>
            Save Preferences
          </button>
        </div>
      </div>
    </div>
  );
}
