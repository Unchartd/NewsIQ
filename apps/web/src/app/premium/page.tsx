"use client";

import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Check, Minus } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { useState } from "react";

export default function PremiumPage() {
  const router = useRouter();
  const { user, isAuthenticated, setUser } = useAuthStore();
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);

  const handleSubscribe = async (plan: "free" | "pro" | "enterprise") => {
    if (!isAuthenticated) {
      toast.error("Please sign in to upgrade.");
      router.push("/login");
      return;
    }

    setLoadingPlan(plan);
    try {
      const response = await apiClient.patch("/users/profile", {
        subscription_plan: plan,
      });
      setUser(response.data);
      toast.success(`Plan updated successfully to ${plan.toUpperCase()}!`);
    } catch {
      toast.error("Failed to update plan.");
    } finally {
      setLoadingPlan(null);
    }
  };

  const plans = [
    {
      name: "Free",
      price: "₹0",
      period: "/month",
      desc: "For occasional readers",
      features: [
        { text: "10 stories/day", included: true },
        { text: "1-line summaries", included: true },
        { text: "Trending feed", included: true },
        { text: "Source comparison", included: false },
        { text: "Personalised feed", included: false },
        { text: "AI chat", included: false },
        { text: "Ad-free", included: false },
      ],
      planKey: "free",
      cta: "Continue free",
      isOutline: true,
    },
    {
      name: "Pro",
      price: "₹399",
      period: "/month",
      desc: "For professionals and power readers",
      features: [
        { text: "Unlimited stories", included: true },
        { text: "All 3 summary depths", included: true },
        { text: "Source comparison table", included: true },
        { text: "Difference Engine", included: true },
        { text: "Personalised feed", included: true },
        { text: "Daily digest", included: true },
        { text: "Ad-free", included: true },
      ],
      planKey: "pro",
      popular: true,
      cta: "Upgrade to Pro",
      isOutline: false,
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "",
      desc: "For newsrooms, analysts, and organisations",
      features: [
        { text: "Everything in Pro", included: true },
        { text: "REST API access", included: true },
        { text: "Bulk story exports", included: true },
        { text: "Advanced analytics", included: true },
        { text: "Dedicated support", included: true },
        { text: "SLA guarantees", included: true },
        { text: "Custom integrations", included: true },
      ],
      planKey: "enterprise",
      cta: "Contact sales",
      isOutline: true,
    },
  ];

  return (
    <AppShell>
      <div style={{ paddingBottom: 60 }}>
        {/* Premium Hero */}
        <div className="niq-premium-hero">
          <div className="niq-premium-eyebrow">NewsIQ Pro</div>
          <h1 className="niq-premium-title">
            Understand more.
            <br />
            Read less.
          </h1>
          <p className="niq-premium-sub">
            Unlock the full intelligence layer — source comparison, personalised feed, and AI-powered story chat.
          </p>
        </div>

        {/* Plans Grid */}
        <div className="niq-plans-grid">
          {plans.map((plan) => {
            const isCurrent = user?.subscription_plan === plan.planKey;
            const isLoading = loadingPlan === plan.planKey;

            return (
              <div
                key={plan.name}
                className={`niq-plan-card ${plan.popular ? "featured" : ""}`}
              >
                {plan.popular && <div className="niq-popular-badge">Most popular</div>}
                
                <div className="niq-plan-name">{plan.name}</div>
                <div className="niq-plan-price">
                  {plan.price}
                  {plan.period && <span style={{ fontSize: 14, fontWeight: 400, color: "var(--ink-3)" }}>{plan.period}</span>}
                </div>
                <div className="niq-plan-desc">{plan.desc}</div>
                
                <ul className="niq-plan-features">
                  {plan.features.map((feat, i) => (
                    <li key={i} className="niq-plan-feature">
                      {feat.included ? (
                        <Check className="w-3.5 h-3.5 text-[#16A34A] shrink-0" style={{ marginTop: 2 }} />
                      ) : (
                        <Minus className="w-3.5 h-3.5 text-gray-300 shrink-0" style={{ marginTop: 2 }} />
                      )}
                      <span style={{ opacity: feat.included ? 1 : 0.5 }}>{feat.text}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  className={`niq-plan-cta ${
                    plan.popular ? "niq-plan-cta-primary" : "niq-plan-cta-outline"
                  }`}
                  disabled={isLoading}
                  onClick={() => {
                    if (plan.planKey === "enterprise") {
                      toast.success("Sales team notified! We will contact you soon.");
                    } else {
                      handleSubscribe(plan.planKey as "free" | "pro" | "enterprise");
                    }
                  }}
                >
                  {isLoading ? "Processing..." : isCurrent ? "Current Plan" : plan.cta}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
