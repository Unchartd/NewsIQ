"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function TosPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/legal?policy=tos");
  }, [router]);

  return (
    <div style={{ padding: "80px", textAlign: "center", color: "var(--ink3)" }}>
      Redirecting to Legal Center...
    </div>
  );
}
