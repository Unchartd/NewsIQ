import type { Metadata } from "next";
import { Suspense } from "react";
import ResetPasswordContent from "./reset-password-content";

export const metadata: Metadata = {
  title: "Reset Password — NewsIQ",
  description: "Reset your NewsIQ account password.",
  robots: { index: false, follow: false },
};

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
