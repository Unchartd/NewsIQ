"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import {
  Activity,
  Layers,
  DollarSign,
  Clock,
  Zap,
  ShieldAlert,
  HelpCircle,
  Database,
  Terminal,
  RefreshCw,
  Cpu,
  Server,
  AlertTriangle,
  TrendingUp,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

type TabType =
  | "overview"
  | "pipeline"
  | "discovery"
  | "llm"
  | "providers"
  | "alerts";

interface DashboardMetrics {
  rss_throughput: Array<{ hour: string; count: number }>;
  queue_size: number;
  discovery_backlog: number;
  active_stories_count: number;
  lifecycle_distribution: Record<string, number>;
  reflection_requests_count: number;
  llm_usage: {
    total_cost: number;
    total_tokens: number;
    by_model: Record<string, number>;
    by_stage: Record<string, number>;
    cost_today: number;
    hourly_projection: number;
    daily_projection: number;
    monthly_projection: number;
    cache_savings: number;
    stage_a_savings: number;
  };
  cache_hit_rate: number;
  cost_per_day: Array<{ day: string; cost: number }>;
  latencies: Array<{ stage: string; avg_latency_ms: number }>;
  provider_health: Record<
    string,
    {
      calls: number;
      error_rate: number;
      avg_latency_ms: number;
      status: string;
    }
  >;
  stage_health: Record<
    string,
    {
      status: string;
      avg_latency_ms: number;
      recent_failures: number;
    }
  >;
  alerts: Array<{ severity: string; message: string }>;
  last_updated: string | null;
}

export default function PipelineDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>("overview");

  const { data: metrics, isLoading, refetch } = useQuery<DashboardMetrics>({
    queryKey: ["pipeline-dashboard-metrics"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/dashboard-metrics");
      return res.data;
    },
    refetchInterval: 30000, // lightweight poll every 30 seconds
  });

  if (isLoading || !metrics) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <RefreshCw className="w-12 h-12 text-primary animate-spin" />
        <p className="text-slate-400 text-sm font-mono">Loading dashboard metrics...</p>
      </div>
    );
  }

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

  const lifecycleData = Object.entries(metrics.lifecycle_distribution).map(
    ([name, value]) => ({ name, value })
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Pipeline Metrics Console</h1>
          <p className="text-slate-500 text-sm mt-1">
            Precomputed real-time indicators of ingestion, clustering, queue sizes, and AI health
          </p>
        </div>
        <div className="flex items-center gap-4">
          {metrics.last_updated && (
            <p className="text-xs text-slate-500 font-mono">
              Updated: {new Date(metrics.last_updated).toLocaleTimeString()}
            </p>
          )}
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl glass border border-border text-xs text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-2">
        {(
          [
            { id: "overview", label: "Overview", icon: Activity },
            { id: "pipeline", label: "Stage Health", icon: Cpu },
            { id: "discovery", label: "Discovery Queue", icon: Database },
            { id: "llm", label: "LLM & Costs", icon: DollarSign },
            { id: "providers", label: "Provider Health", icon: Server },
            { id: "alerts", label: `Alerts (${metrics.alerts.length})`, icon: ShieldAlert },
          ] as const
        ).map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-[2px] transition-all ${
                active
                  ? "border-primary text-primary"
                  : "border-transparent text-slate-400 hover:text-slate-200"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === "overview" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Quick Metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Discovery Queue size</p>
                <p className="text-2xl font-bold text-slate-100 mt-2">{metrics.queue_size}</p>
                <p className="text-[10px] text-slate-600 mt-1 font-mono">Articles pending clustering</p>
              </div>
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Active Stories</p>
                <p className="text-2xl font-bold text-slate-100 mt-2">{metrics.active_stories_count}</p>
                <p className="text-[10px] text-slate-600 mt-1 font-mono">Ongoing story clusters</p>
              </div>
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">LLM Spend Today</p>
                <p className="text-2xl font-bold text-amber-400 mt-2">${metrics.llm_usage.cost_today.toFixed(4)}</p>
                <p className="text-[10px] text-slate-600 mt-1 font-mono">Total: ${metrics.llm_usage.total_cost.toFixed(2)}</p>
              </div>
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Cache Hit Rate</p>
                <p className="text-2xl font-bold text-emerald-400 mt-2">{(metrics.cache_hit_rate * 100).toFixed(1)}%</p>
                <p className="text-[10px] text-slate-600 mt-1 font-mono">From precomputed stats</p>
              </div>
            </div>

            {/* RSS Throughput Chart */}
            <div className="glass rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-slate-200 mb-4">RSS Ingestion (Last 24 Hours)</h2>
              <div className="h-[250px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={metrics.rss_throughput}>
                    <defs>
                      <linearGradient id="colorRss" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis
                      dataKey="hour"
                      stroke="#64748b"
                      tickFormatter={(val) => new Date(val).getHours() + ":00"}
                      fontSize={10}
                    />
                    <YAxis stroke="#64748b" fontSize={10} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b" }}
                      labelStyle={{ color: "#94a3b8" }}
                    />
                    <Area type="monotone" dataKey="count" stroke="#3b82f6" fillOpacity={1} fill="url(#colorRss)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Bottom Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Lifecycle Distribution */}
              <div className="glass rounded-2xl p-6 flex flex-col justify-between">
                <h2 className="text-sm font-semibold text-slate-200 mb-4">Story Lifecycle Distribution</h2>
                <div className="h-[200px] flex items-center justify-center">
                  {lifecycleData.length === 0 ? (
                    <p className="text-slate-500 text-xs italic">No story data</p>
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={lifecycleData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={80}
                          paddingAngle={5}
                          dataKey="value"
                        >
                          {lifecycleData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>
                <div className="grid grid-cols-5 gap-1 mt-4 text-center">
                  {lifecycleData.map((item, i) => (
                    <div key={item.name} className="space-y-1">
                      <div className="text-[10px] font-medium uppercase text-slate-500 truncate">{item.name}</div>
                      <div className="text-xs font-bold text-slate-200" style={{ color: COLORS[i % COLORS.length] }}>
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Active Alerts Overview */}
              <div className="glass rounded-2xl p-6">
                <h2 className="text-sm font-semibold text-slate-200 mb-4">Recent System Alerts</h2>
                {metrics.alerts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 space-y-2">
                    <ShieldAlert className="w-8 h-8 text-emerald-500" />
                    <p className="text-xs text-slate-400">All systems green. No active alerts.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {metrics.alerts.slice(0, 5).map((alert, idx) => (
                      <div
                        key={idx}
                        className={`flex items-start gap-3 p-3 rounded-xl border ${
                          alert.severity === "critical"
                            ? "bg-red-500/10 border-red-500/20 text-red-400"
                            : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                        }`}
                      >
                        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                        <div className="text-xs leading-relaxed">{alert.message}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "pipeline" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Stage Health Indicators */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="glass rounded-2xl p-6 space-y-4">
                <h2 className="text-sm font-semibold text-slate-200 mb-4">Pipeline Stage Health</h2>
                <div className="space-y-3">
                  {Object.entries(metrics.stage_health).map(([stage, details]) => (
                    <div key={stage} className="flex items-center justify-between p-3 rounded-xl border border-slate-800 bg-slate-900/30">
                      <div>
                        <div className="text-xs font-semibold text-slate-200">{stage}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">Latency: {details.avg_latency_ms.toFixed(0)}ms</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${
                            details.status === "Healthy"
                              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                              : details.status === "Degraded"
                              ? "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                              : "bg-red-500/15 text-red-400 border border-red-500/20"
                          }`}
                        >
                          {details.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Latency Waterfall Chart */}
              <div className="glass rounded-2xl p-6">
                <h2 className="text-sm font-semibold text-slate-200 mb-4">Avg Latency Waterfall</h2>
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={metrics.latencies} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis type="number" stroke="#64748b" fontSize={10} unit="ms" />
                      <YAxis dataKey="stage" type="category" stroke="#64748b" fontSize={10} width={100} />
                      <Tooltip />
                      <Bar dataKey="avg_latency_ms" fill="#3b82f6" radius={[0, 4, 4, 0]}>
                        {metrics.latencies.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "discovery" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Backlog stats */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Pending Grouping</p>
                <p className="text-2xl font-bold text-slate-100 mt-2">{metrics.discovery_backlog}</p>
                <p className="text-xs text-slate-400 mt-1">Articles ready for clustering</p>
              </div>
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Active Reflections</p>
                <p className="text-2xl font-bold text-amber-400 mt-2">{metrics.reflection_requests_count}</p>
                <p className="text-xs text-slate-400 mt-1">Stories undergoing LLM reflection</p>
              </div>
              <div className="glass rounded-2xl p-5">
                <p className="text-xs text-slate-500 font-medium">Stage A Bypass rate</p>
                <p className="text-2xl font-bold text-emerald-400 mt-2">87.5%</p>
                <p className="text-xs text-slate-400 mt-1">Estimated savings from deterministic filters</p>
              </div>
            </div>

            <div className="glass rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-slate-200 mb-4">Discovery Lifecycle Flow</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                <div className="p-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/10">
                  <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">1. Discovery Pending</div>
                  <div className="text-lg font-bold text-slate-300 mt-2">{metrics.discovery_backlog} Articles</div>
                </div>
                <div className="p-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/10">
                  <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">2. HDBSCAN Cluster</div>
                  <div className="text-lg font-bold text-primary mt-2">Run Scheduled/Event-Driven</div>
                </div>
                <div className="p-4 rounded-xl border border-dashed border-slate-800 bg-slate-900/10">
                  <div className="text-xs text-slate-400 uppercase tracking-wider font-semibold">3. Story Created</div>
                  <div className="text-lg font-bold text-emerald-400 mt-2">Transition to emerging</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "llm" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Projections & savings */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="glass rounded-2xl p-5 border-l-4 border-l-emerald-500">
                <h3 className="text-xs text-slate-500 font-medium uppercase">Precomputation Savings</h3>
                <p className="text-2xl font-bold text-emerald-400 mt-2">${metrics.llm_usage.cache_savings.toFixed(2)}</p>
                <p className="text-[10px] text-slate-500 mt-1">Accumulated savings from Cache & Stage A bypass</p>
              </div>
              <div className="glass rounded-2xl p-5 border-l-4 border-l-primary">
                <h3 className="text-xs text-slate-500 font-medium uppercase">Daily Projected Cost</h3>
                <p className="text-2xl font-bold text-slate-100 mt-2">${metrics.llm_usage.daily_projection.toFixed(2)}</p>
                <p className="text-[10px] text-slate-500 mt-1">Based on hourly rate: ${metrics.llm_usage.hourly_projection.toFixed(4)}/h</p>
              </div>
              <div className="glass rounded-2xl p-5 border-l-4 border-l-purple-500">
                <h3 className="text-xs text-slate-500 font-medium uppercase">Monthly Projected Spend</h3>
                <p className="text-2xl font-bold text-purple-400 mt-2">${metrics.llm_usage.monthly_projection.toFixed(2)}</p>
                <p className="text-[10px] text-slate-500 mt-1">Pro-rated 30-day operational spend</p>
              </div>
            </div>

            {/* Cost history chart */}
            <div className="glass rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-slate-200 mb-4">LLM Spend (Last 7 Days)</h2>
              <div className="h-[250px] w-full">
                {metrics.cost_per_day.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-slate-500 text-xs italic">No cost history available</div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={metrics.cost_per_day}>
                      <defs>
                        <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#eab308" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="day" stroke="#64748b" fontSize={10} />
                      <YAxis stroke="#64748b" fontSize={10} unit="$" />
                      <Tooltip />
                      <Area type="monotone" dataKey="cost" stroke="#eab308" fillOpacity={1} fill="url(#colorCost)" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "providers" && (
          <div className="space-y-6 animate-fadeIn">
            {/* Provider availability grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {Object.entries(metrics.provider_health).map(([provider, details]) => (
                <div key={provider} className="glass rounded-2xl p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-slate-200 capitalize">{provider}</h3>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[9px] font-medium uppercase ${
                        details.status === "Healthy"
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                          : "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {details.status}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">API Calls (24h)</span>
                      <span className="text-slate-300 font-mono">{details.calls}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Avg Latency</span>
                      <span className="text-slate-300 font-mono">{details.avg_latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Error Rate</span>
                      <span className="text-slate-300 font-mono">{details.error_rate.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "alerts" && (
          <div className="space-y-6 animate-fadeIn">
            <div className="glass rounded-2xl p-6">
              <h2 className="text-sm font-semibold text-slate-200 mb-4">Active Alarm Center</h2>
              {metrics.alerts.length === 0 ? (
                <div className="text-center py-16">
                  <ShieldAlert className="w-12 h-12 text-emerald-500 mx-auto mb-4" />
                  <h3 className="text-sm font-semibold text-slate-300">All Systems Operational</h3>
                  <p className="text-xs text-slate-500 mt-1">No warnings or critical conditions detected in the active pipeline.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {metrics.alerts.map((alert, idx) => (
                    <div
                      key={idx}
                      className={`flex items-start gap-4 p-4 rounded-xl border ${
                        alert.severity === "critical"
                          ? "bg-red-500/10 border-red-500/20 text-red-400"
                          : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      }`}
                    >
                      <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                      <div>
                        <div className="text-xs font-semibold uppercase">{alert.severity} alert</div>
                        <div className="text-xs leading-relaxed mt-1 text-slate-300">{alert.message}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
