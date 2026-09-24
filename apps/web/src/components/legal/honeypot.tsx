"use client";

/**
 * Invisible field that people never fill in but form-filling bots do. The
 * legal-request API silently drops submissions where it is set, keeping spam
 * out of the inbox without a CAPTCHA.
 */
export function Honeypot({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="text"
      name="website"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      tabIndex={-1}
      autoComplete="off"
      aria-hidden="true"
      style={{ position: "absolute", left: "-10000px", width: 1, height: 1, opacity: 0 }}
    />
  );
}
