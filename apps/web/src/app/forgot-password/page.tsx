import type { Metadata } from "next";
import ForgotPasswordContent from "./forgot-password-content";

export const metadata: Metadata = {
  title: "Forgot Password — NewsIQ",
  description: "Reset your NewsIQ account password.",
  robots: { index: false, follow: false },
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordContent />;
}
