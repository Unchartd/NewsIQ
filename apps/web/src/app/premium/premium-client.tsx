"use client";

import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Check, Minus } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { legalRequestErrorMessage, submitLegalRequest } from "@/lib/legal-requests";
import { toast } from "sonner";
import { useState } from "react";

export default function PremiumPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);

  // Paid plans are not live. This used to PATCH subscription_plan (which the
  // API deliberately ignores) and then announce "Plan updated successfully to
  // PRO!", and "Contact sales" announced "Sales team notified!" without
  // notifying anyone. Both now register real interest in the inbox.
  const handleInterest = async (plan: "pro" | "enterprise") => {
    if (!isAuthenticated || !user?.email) {
      toast.info("Sign in and we'll email you when paid plans launch.");
      router.push("/login?redirect=/premium");
      return;
    }
    setLoadingPlan(plan);
    try {
      await submitLegalRequest({
        kind: "contact",
        request_type: `${plan}-interest`,
        email: user.email,
        subject: plan === "pro" ? "Notify me when Pro launches" : "Enterprise enquiry",
        details: `${user.email} asked to hear about the ${plan} plan.`,
      });
      toast.success(
        plan === "pro" ? "Thanks! We'll email you when Pro launches." : "Thanks! We'll reply by email."
      );
    } catch (err) {
      toast.error(legalRequestErrorMessage(err));
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
        { text: "Ad-free", included: true },
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
      cta: "Notify me at launch",
      isOutline: false,
    },
    {
      name: "Enterprise",
      price: "Custom",
      period: "",
      desc: "For newsrooms, organisations",
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
      cta: "Get in touch",
      isOutline: true,
    },
  ];

  return (
    <AppShell>
      <div style={{ paddingBottom: 60 }}>
        {/* Premium Hero */}
        <div className="pm-hero">
          <div className="pm-ey">NewsIQ Pro</div>
          <h1 className="pm-title">
            Understand more.
            <br />
            Read less.
          </h1>
          <p className="pm-sub">
            Unlock the full intelligence layer — source comparison, personalised feed, and AI-powered story chat.
          </p>
          <p className="pm-sub" style={{ fontWeight: 600 }}>
            Paid plans are coming soon. During early access every feature is free, and we take no payments.
          </p>
        </div>

        {/* Plans Grid */}
        <div className="plans">
          {plans.map((plan) => {
            const isCurrent = user?.subscription_plan === plan.planKey;
            const isLoading = loadingPlan === plan.planKey;

            return (
              <div
                key={plan.name}
                className={`plan ${plan.popular ? "feat" : ""}`}
              >
                {plan.popular && <div className="pop-badge">Most popular</div>}
                
                <div className="pn">{plan.name}</div>
                <div className="pp">
                  {plan.price}
                  {plan.period && <span>{plan.period}</span>}
                </div>
                <div className="pd">{plan.desc}</div>
                
                <ul className="pf">
                  {plan.features.map((feat, i) => (
                    <li key={i} className="pfi">
                      {feat.included ? (
                        <Check className="pfc shrink-0" size={14} style={{ marginTop: 2 }} />
                      ) : (
                        <Minus className="pfd shrink-0" size={14} style={{ marginTop: 2 }} />
                      )}
                      <span style={{ opacity: feat.included ? 1 : 0.5 }}>{feat.text}</span>
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  className={`pcta ${plan.popular ? "pctap" : "pctao"}`}
                  disabled={isLoading}
                  onClick={() => {
                    if (plan.planKey === "free") {
                      router.push("/home");
                    } else {
                      handleInterest(plan.planKey as "pro" | "enterprise");
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
