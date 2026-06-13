import type { Metadata } from "next";
import { Suspense } from "react";
import VerifyEmailContent from "./verify-email-content";

export const metadata: Metadata = {
  title: "Verify Email — NewsIQ",
  description: "Verify your NewsIQ account email address.",
  robots: { index: false, follow: false },
};

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
