"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, Star, ShieldAlert, Sparkles, Building } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";

export default function PremiumPage() {
  const { user, isAuthenticated, setUser } = useAuthStore();
  const queryClient = useQueryClient();

  const handleSubscribe = async (plan: "free" | "pro" | "enterprise") => {
    if (!isAuthenticated) {
      toast.error("Please sign in to select a plan.");
      window.location.href = "/login";
      return;
    }

    try {
      // Simulate upgrading/subscribing by PATCHing user profile subscription_plan
      const response = await apiClient.patch("/users/profile", {
        subscription_plan: plan,
      });
      
      setUser(response.data);
      toast.success(`Successfully subscribed to the ${plan.toUpperCase()} plan!`);
    } catch {
      toast.error("Subscription simulation failed.");
    }
  };

  const plans = [
    {
      name: "Free",
      price: "$0",
      description: "Essential intelligence for casual readers.",
      icon: Star,
      features: [
        "View aggregated news stories",
        "Basic 1-line and Short summaries",
        "Source transparency overview",
        "Chronological timeline",
      ],
      planKey: "free",
    },
    {
      name: "Pro",
      price: "$9",
      period: "/mo",
      description: "Deep analytics and detailed context for power users.",
      icon: Sparkles,
      features: [
        "Everything in Free",
        "Unlimited Detailed summaries",
        "Full publisher differences analysis",
        "Key facts extraction",
        "Daily personalized digests",
        "Priority feed loading",
      ],
      popular: true,
      planKey: "pro",
    },
    {
      name: "Enterprise",
      price: "$49",
      period: "/mo",
      description: "News analytics & API access for organizations.",
      icon: Building,
      features: [
        "Everything in Pro",
        "Developer API Keys access",
        "100k requests / month rate limit",
        "Custom source ingestion requests",
        "Dedicated account support",
      ],
      planKey: "enterprise",
    },
  ];

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-8 pb-24">
        {/* Title */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
            Upgrade Your News Intelligence
          </h1>
          <p className="text-muted-foreground text-sm max-w-xl mx-auto">
            Choose the plan that fits your reading depth. Get neutral, AI-synthesized updates on global events.
          </p>
        </div>

        {/* Pricing Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
          {plans.map((plan) => {
            const Icon = plan.icon;
            const isCurrent =
              (plan.planKey === "free" && user?.subscription_plan === "free") ||
              (plan.planKey === "pro" && user?.subscription_plan === "pro") ||
              (plan.planKey === "enterprise" && user?.subscription_plan === "enterprise");

            return (
              <Card
                key={plan.name}
                className={`relative border-border/50 rounded-2xl flex flex-col justify-between overflow-hidden ${
                  plan.popular ? "ring-2 ring-primary bg-primary/5 dark:bg-primary/5" : ""
                }`}
              >
                {plan.popular && (
                  <div className="absolute top-3 right-3">
                    <Badge variant="default" className="text-[10px] rounded-full uppercase tracking-wider px-2 py-0.5">
                      Most Popular
                    </Badge>
                  </div>
                )}
                
                <div>
                  <CardHeader className="p-6">
                    <div className="flex items-center gap-2">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                        plan.popular ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"
                      }`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <CardTitle className="text-base font-bold">{plan.name}</CardTitle>
                    </div>
                    
                    <div className="flex items-baseline gap-0.5 mt-4">
                      <span className="text-3xl font-bold tracking-tight text-foreground">{plan.price}</span>
                      {plan.period && (
                        <span className="text-xs text-muted-foreground font-medium">{plan.period}</span>
                      )}
                    </div>
                    <CardDescription className="mt-2 text-xs leading-relaxed">
                      {plan.description}
                    </CardDescription>
                  </CardHeader>
                  
                  <CardContent className="px-6 pb-6 pt-0">
                    <ul className="space-y-2.5 text-xs text-muted-foreground">
                      {plan.features.map((feat) => (
                        <li key={feat} className="flex items-start gap-2 leading-relaxed">
                          <Check className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                          <span>{feat}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </div>

                <CardFooter className="p-6 pt-0">
                  <Button
                    onClick={() => handleSubscribe(plan.planKey as any)}
                    variant={plan.popular ? "default" : "outline"}
                    className="w-full rounded-xl"
                  >
                    {isCurrent ? "Current Plan" : `Select ${plan.name}`}
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
