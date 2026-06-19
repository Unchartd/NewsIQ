"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function PrivacyPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/legal?policy=privacy");
  }, [router]);

  return (
    <div style={{ padding: "80px", textAlign: "center", color: "var(--ink3)" }}>
      Redirecting to Legal Center...
    </div>
  );
}
