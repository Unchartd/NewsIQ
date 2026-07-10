"use client";

import { BRANDING } from "@/branding/constants";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { AlertTriangle, Clock, RefreshCw, BarChart2, CheckCircle2, ShieldCheck, HeartPulse, Sparkles } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  Legend,
} from "recharts";

interface DailyTrendItem {
  date: string;
  failures: number;
  successes: number;
  failureRate: number;
}

interface ProviderHealthItem {
  provider: string;
  totalCalls: number;
  failedCalls: number;
  successRate: number;
}

interface TopStageItem {
  stage: string;
  count: number;
}

interface CommonProviderFailureItem {
  provider: string;
  count: number;
}

interface FailureAnalyticsData {
  totalFailures: number;
  resolvedFailures: number;
  unresolvedFailures: number;
  topFailingStages: TopStageItem[];
  mostCommonProviderFailures: CommonProviderFailureItem[];
  quotaErrorCount: number;
  rateLimitErrorCount: number;
  avgRetries: number;
  dailyTrends: DailyTrendItem[];
  providerHealth: ProviderHealthItem[];
}

const BAR_COLORS = ["#e8334a", "#f43f5e", "#fb7185", "#f59e0b", "#3b82f6", "#8b5cf6", "#64748b"];

export default function FailureAnalyticsPage() {
  const { data, isLoading, refetch } = useQuery<FailureAnalyticsData>({
    queryKey: ["failure-analytics"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/failure-analytics");
      return res.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const dailyTrendData = data?.dailyTrends ?? [];
  const topStageData = data?.topFailingStages
    ? data.topFailingStages.map((item) => ({
        stage: item.stage.replace("_", " "),
        count: item.count,
      }))
    : [];

  const providerHealthData = data?.providerHealth ?? [];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <HeartPulse className="w-6 h-6 text-primary" />
            Failure & Health Analytics
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            System stability rates, provider performance logs, and daily error trends.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 self-start transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Stats
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Failures", value: data?.totalFailures ?? "—", icon: AlertTriangle, color: "text-red-400 bg-red-500/10" },
          { label: "Active Unresolved", value: data?.unresolvedFailures ?? "—", icon: Clock, color: "text-amber-400 bg-amber-500/10" },
          { label: "Resolved Errors", value: data?.resolvedFailures ?? "—", icon: CheckCircle2, color: "text-emerald-400 bg-emerald-500/10" },
          { label: "Avg Retry Attempts", value: data?.avgRetries ?? "—", icon: RefreshCw, color: "text-blue-400 bg-blue-500/10" },
        ].map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="glass rounded-2xl p-5 flex flex-col justify-between">
              <div className="flex items-center justify-between mb-4">
                <span className="text-slate-500 text-xs font-medium">{c.label}</span>
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${c.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
              </div>
              <p className="text-3xl font-bold text-slate-100 tabular-nums">
                {isLoading ? "—" : c.value}
              </p>
            </div>
          );
        })}
      </div>

      {/* Daily trend area chart */}
      <div className="glass rounded-2xl p-5 border border-white/5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-primary" /> Daily Pipeline Success vs Failure Volume (14 days)
        </h2>
        {isLoading ? (
          <div className="h-64 flex items-center justify-center text-slate-500 text-xs">
            Loading trend charts...
          </div>
        ) : dailyTrendData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-slate-655 text-xs">
            No pipeline runs tracked.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={dailyTrendData} margin={{ left: 10, right: 10, top: 10, bottom: 0 }}>
              <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 9 }} tickFormatter={(d) => d.slice(5)} />
              <YAxis tick={{ fill: "#64748b", fontSize: 9 }} />
              <Tooltip
                contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 11 }}
              />
              <Legend verticalAlign="top" height={36} iconType="circle" iconSize={8} formatter={(v) => <span className="text-slate-400 text-xs capitalize">{v}</span>} />
              <Area type="monotone" dataKey="successes" name="Successes" stroke="#10b981" fillOpacity={0.06} fill="url(#colorSuccess)" />
              <Area type="monotone" dataKey="failures" name="Failures" stroke="var(--brand-primary)" fillOpacity={0.06} fill="url(#colorFailure)" />
              <defs>
                <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorFailure" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--brand-primary)" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="var(--brand-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Lower split charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Failing Stages */}
        <div className="glass rounded-2xl p-5 border border-white/5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" /> Errors by Pipeline Stage
          </h2>
          {isLoading ? (
            <div className="h-60 flex items-center justify-center text-slate-500 text-xs">
              Loading stage diagnostics...
            </div>
          ) : topStageData.length === 0 ? (
            <div className="h-60 flex items-center justify-center text-slate-655 text-xs">
              No errors logged yet.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={topStageData} layout="vertical" margin={{ left: 20, right: 20, top: 0, bottom: 0 }}>
                <XAxis type="number" tick={{ fill: "#64748b", fontSize: 9 }} />
                <YAxis type="category" dataKey="stage" tick={{ fill: "#94a3b8", fontSize: 9 }} width={120} />
                <Tooltip
                  contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 11 }}
                />
                <Bar dataKey="count" fill="#e8334a" radius={[0, 4, 4, 0]}>
                  {topStageData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Provider Health Success Rates */}
        <div className="glass rounded-2xl p-5 border border-white/5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" /> LLM Provider Reliability & Success Rates
          </h2>
          {isLoading ? (
            <div className="h-60 flex items-center justify-center text-slate-500 text-xs">
              Loading provider telemetry...
            </div>
          ) : providerHealthData.length === 0 ? (
            <div className="h-60 flex items-center justify-center text-slate-655 text-xs">
              No LLM traces available yet.
            </div>
          ) : (
            <div className="space-y-4 py-2">
              {providerHealthData.map((p) => {
                const isHealthy = p.successRate >= 95;
                const isWarning = p.successRate < 95 && p.successRate >= 80;
                const rateColor = isHealthy
                  ? "text-emerald-400"
                  : isWarning
                  ? "text-amber-400"
                  : "text-red-400";
                const barColor = isHealthy
                  ? "bg-emerald-500"
                  : isWarning
                  ? "bg-amber-500"
                  : "bg-red-500";

                return (
                  <div key={p.provider} className="bg-white/2 border border-white/5 rounded-xl p-4">
                    <div className="flex justify-between items-center mb-2">
                      <div>
                        <span className="text-xs font-bold text-slate-200 capitalize">
                          {p.provider} Gateway
                        </span>
                        <span className="text-[10px] text-slate-500 ml-2">
                          ({p.totalCalls.toLocaleString()} total requests)
                        </span>
                      </div>
                      <span className={`text-xs font-bold ${rateColor}`}>
                        {p.successRate.toFixed(1)}% Success
                      </span>
                    </div>
                    {/* Progress bar */}
                    <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${barColor} transition-all duration-500`}
                        style={{ width: `${p.successRate}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-[9px] text-slate-500 mt-1">
                      <span>{p.totalCalls - p.failedCalls} Succeeded</span>
                      <span>{p.failedCalls} Failed</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Quota errors notification box */}
      {(data?.quotaErrorCount ?? 0) > 0 && (
        <div className="glass rounded-2xl p-5 border border-red-500/10 flex items-start gap-4 bg-red-500/5">
          <Sparkles className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-red-400">Quota Limit Exceeded Alert</h3>
            <p className="text-xs text-slate-400 mt-1">
              {BRANDING.NAME} has hit provider-specific API credit/token quota limits{" "}
              <span className="font-bold font-mono text-red-400">
                {data?.quotaErrorCount} times
              </span>{" "}
              over the tracked history. Make sure to check API keys on build.nvidia.com or Google Cloud Console billing setup.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
