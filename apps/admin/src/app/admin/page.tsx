"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useSSE } from "@/lib/useSSE";
import {
  Activity,
  GitBranch,
  DollarSign,
  Layers,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
  ArrowUpRight,
  Database,
  ShieldAlert,
  Server,
} from "lucide-react";
import Link from "next/link";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

interface PipelineStatus {
  active_runs: number;
  completed_today: number;
  failed_today: number;
  avg_duration_ms: number;
  stages: Array<{
    stage: string;
    status: string;
    count: number;
  }>;
}

interface CostAnalytics {
  total_cost_usd: number;
  by_stage: Record<string, number>;
  by_model: Record<string, number>;
  total_tokens: number;
}

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
  href,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  color: string;
  href?: string;
}) {
  const inner = (
    <div className="glass rounded-2xl p-5 hover:glass-hover transition-all group cursor-pointer glow-primary">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-5 h-5" />
        </div>
        {href && (
          <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors" />
        )}
      </div>
      <p className="text-2xl font-bold text-slate-100 tabular-nums">{value}</p>
      <p className="text-xs text-slate-500 mt-1 font-medium">{label}</p>
      {sub && <p className="text-[10px] text-slate-600 mt-0.5">{sub}</p>}
    </div>
  );

  return href ? <Link href={href}>{inner}</Link> : inner;
}

function RecentEventRow({ event }: { event: { stage: string; status: string; run_id: string; duration_ms?: number } }) {
  const statusConfig: Record<string, { label: string; cls: string }> = {
    success: { label: "Success", cls: "badge-success" },
    failed: { label: "Failed", cls: "badge-danger" },
    running: { label: "Running", cls: "badge-primary" },
    pending: { label: "Pending", cls: "badge-neutral" },
    skipped: { label: "Skipped", cls: "badge-neutral" },
  };

  const cfg = statusConfig[event.status] ?? statusConfig.pending;

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border last:border-0">
      <span className={`badge ${cfg.cls}`}>{cfg.label}</span>
      <span className="text-xs text-slate-300 font-mono flex-1 truncate">{event.stage}</span>
      <span className="text-[10px] text-slate-655 font-mono truncate max-w-[120px]">
        {event.run_id?.slice(0, 8)}…
      </span>
      {event.duration_ms && (
        <span className="text-[10px] text-slate-550 font-mono whitespace-nowrap">
          {event.duration_ms}ms
        </span>
      )}
    </div>
  );
}

export default function DashboardHome() {
  const { events, status: sseStatus } = useSSE();

  const { data: pipelineStatus } = useQuery<PipelineStatus>({
    queryKey: ["pipeline-status"],
    queryFn: async () => {
      const [statusRes, metricsRes] = await Promise.all([
        apiClient.get("/admin/pipeline/status"),
        apiClient.get("/admin/metrics/summary"),
      ]);
      const statusData = statusRes.data;
      const metricsData = metricsRes.data;
      
      const active_runs = statusData.status === "running" ? 1 : 0;
      const failed_today = metricsData.failed_runs_count ?? 0;
      const total_runs = metricsData.total_pipeline_runs ?? 0;
      const completed_today = Math.max(0, total_runs - failed_today);
      
      let avg_duration_ms = 0;
      if (statusData.stages && statusData.stages.length > 0) {
        const completedStages = statusData.stages.filter((s: any) => s.completed_at && s.started_at);
        if (completedStages.length > 0) {
          const totalDuration = completedStages.reduce((sum: number, s: any) => {
            const start = new Date(s.started_at).getTime();
            const end = new Date(s.completed_at).getTime();
            return sum + Math.max(0, end - start);
          }, 0);
          avg_duration_ms = totalDuration / completedStages.length;
        }
      }
      
      return {
        active_runs,
        completed_today,
        failed_today,
        avg_duration_ms,
        stages: statusData.stages || [],
      };
    },
    refetchInterval: 15000,
  });

  const { data: costs } = useQuery<CostAnalytics>({
    queryKey: ["cost-analytics"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/costs");
      const rawData = res.data;
      const breakdown = rawData?.breakdown ?? [];
      const total_cost_usd = rawData?.total_cost_usd ?? 0.0;
      
      let total_tokens = 0;
      const by_stage: Record<string, number> = {};
      const by_model: Record<string, number> = {};
      
      for (const item of breakdown) {
        const tokens = (item.input_tokens || 0) + (item.output_tokens || 0);
        total_tokens += tokens;
        
        by_stage[item.stage] = (by_stage[item.stage] || 0) + (item.cost_usd || 0);
        by_model[item.model] = (by_model[item.model] || 0) + (item.cost_usd || 0);
      }
      
      return {
        total_cost_usd,
        total_tokens,
        by_stage,
        by_model,
      };
    },
    refetchInterval: 60000,
  });

  const { data: storiesCount } = useQuery<{ total: number }>({
    queryKey: ["stories-count"],
    queryFn: async () => {
      const res = await apiClient.get("/stories", { params: { limit: 1 } });
      const raw = Array.isArray(res.data) ? res.data : [];
      return { total: raw.length };
    },
  });

  const { data: metrics } = useQuery<any>({
    queryKey: ["pipeline-dashboard-metrics"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/dashboard-metrics");
      return res.data;
    },
    refetchInterval: 30000,
  });

  const failureRate =
    pipelineStatus && pipelineStatus.completed_today + pipelineStatus.failed_today > 0
      ? (
          (pipelineStatus.failed_today /
            (pipelineStatus.completed_today + pipelineStatus.failed_today)) *
          100
        ).toFixed(1)
      : "0.0";

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
  const lifecycleData: Array<{ name: string; value: number }> = metrics?.lifecycle_distribution
    ? Object.entries(metrics.lifecycle_distribution).map(([name, value]) => ({ name, value: value as number }))
    : [];

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">System Overview</h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time AI pipeline observability and health metrics
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl glass border border-border text-xs">
          <span
            className={`w-2 h-2 rounded-full ${
              sseStatus === "connected"
                ? "bg-emerald-500 animate-pulse"
                : "bg-slate-650"
            }`}
          />
          <span className="text-slate-400 font-mono capitalize">{sseStatus}</span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Active Pipeline Runs"
          value={pipelineStatus?.active_runs ?? "—"}
          sub="Currently running"
          icon={Activity}
          color="bg-primary/15 text-primary"
          href="/admin/pipeline"
        />
        <StatCard
          label="Completed Today"
          value={pipelineStatus?.completed_today ?? "—"}
          sub={`${failureRate}% failure rate`}
          icon={CheckCircle2}
          color="bg-emerald-500/15 text-emerald-400"
          href="/admin/pipeline"
        />
        <StatCard
          label="Total Stories"
          value={storiesCount?.total ?? "—"}
          sub="In story cluster database"
          icon={Layers}
          color="bg-primary/15 text-primary"
          href="/admin/stories"
        />
        <StatCard
          label="Cost Today (USD)"
          value={metrics?.llm_usage ? `$${metrics.llm_usage.cost_today.toFixed(4)}` : "—"}
          sub={`${metrics?.llm_usage?.tokens_today?.toLocaleString() ?? "—"} tokens`}
          icon={DollarSign}
          color="bg-amber-500/15 text-amber-400"
          href="/admin/costs"
        />
      </div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <StatCard
          label="Failed Runs Today"
          value={pipelineStatus?.failed_today ?? "—"}
          icon={AlertTriangle}
          color="bg-red-500/15 text-red-400"
          href="/admin/pipeline"
        />
        <StatCard
          label="Avg Duration"
          value={
            pipelineStatus?.avg_duration_ms
              ? `${(pipelineStatus.avg_duration_ms / 1000).toFixed(1)}s`
              : "—"
          }
          sub="Per pipeline run"
          icon={Clock}
          color="bg-blue-500/15 text-blue-400"
        />
        <StatCard
          label="Tokens Used Today"
          value={metrics?.llm_usage?.tokens_today?.toLocaleString() ?? "—"}
          sub="Across all LLM calls today"
          icon={Zap}
          color="bg-pink-500/15 text-pink-400"
          href="/admin/costs"
        />
      </div>

      {/* Discovery & Queue Status */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Discovery Queue"
          value={metrics?.discovery_queue_size ?? "—"}
          sub="Articles pending clustering"
          icon={Database}
          color="bg-indigo-500/15 text-indigo-400"
        />
        <StatCard
          label="Crawl Backlog"
          value={metrics?.discovery_backlog ?? "—"}
          sub="URLs pending download"
          icon={Server}
          color="bg-cyan-500/15 text-cyan-400"
        />
        <StatCard
          label="Active Reflections"
          value={metrics?.reflection_requests_count ?? "—"}
          sub="Stories in synthesis loop"
          icon={Activity}
          color="bg-purple-500/15 text-purple-400"
        />
        <StatCard
          label="Cache Hit Rate"
          value={metrics ? `${(metrics.cache_hit_rate * 100).toFixed(1)}%` : "—"}
          sub="Savings from bypass"
          icon={Zap}
          color="bg-emerald-500/15 text-emerald-400"
        />
      </div>

      {/* Live pipeline events & Cost breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent SSE events */}
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-primary" />
                Live Pipeline Events
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Last {Math.min(events.length, 10)} events via SSE stream
              </p>
            </div>
            <Link
              href="/admin/pipeline"
              className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
            >
              View DAG <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          {events.length === 0 ? (
            <div className="text-center py-8">
              <Activity className="w-8 h-8 text-slate-700 mx-auto mb-2" />
              <p className="text-xs text-slate-655">
                {sseStatus === "connecting"
                  ? "Connecting to live stream…"
                  : "No pipeline events yet. Trigger an ingestion run."}
              </p>
            </div>
          ) : (
            <div>
              {events.slice(0, 10).map((ev, i) => (
                <RecentEventRow key={i} event={ev} />
              ))}
            </div>
          )}
        </div>

        {/* Cost by model */}
        <div className="glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-amber-400" />
                Cost by AI Model
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">Cumulative spend breakdown</p>
            </div>
            <Link
              href="/admin/costs"
              className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
            >
              Full Report <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          {!costs?.by_model || Object.keys(costs.by_model).length === 0 ? (
            <div className="text-center py-8">
              <DollarSign className="w-8 h-8 text-slate-700 mx-auto mb-2" />
              <p className="text-xs text-slate-655">No cost data yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(costs.by_model)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 6)
                .map(([model, cost]) => {
                  const maxCost = Math.max(...Object.values(costs.by_model));
                  const pct = (cost / maxCost) * 100;
                  return (
                    <div key={model}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs text-slate-400 font-mono truncate">{model}</span>
                        <span className="text-xs text-slate-300 font-mono ml-2 shrink-0">
                          ${cost.toFixed(4)}
                        </span>
                      </div>
                      <div className="h-1.5 bg-border rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-primary to-rose-500 rounded-full transition-all duration-700"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>

      {/* RSS Throughput & Lifecycle charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* RSS Throughput */}
        <div className="glass rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">RSS Ingestion Throughput (Last 24 Hours)</h2>
          <div className="h-[250px] w-full">
            {!metrics?.rss_throughput || metrics.rss_throughput.length === 0 ? (
              <div className="flex items-center justify-center h-full text-slate-500 text-xs italic">
                No ingestion data available
              </div>
            ) : (
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
                  <ChartTooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Area type="monotone" dataKey="count" stroke="#3b82f6" fillOpacity={1} fill="url(#colorRss)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Lifecycle Distribution */}
        <div className="glass rounded-2xl p-5 flex flex-col justify-between">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">Story Lifecycle Distribution</h2>
          <div className="h-[180px] flex items-center justify-center">
            {lifecycleData.length === 0 ? (
              <p className="text-slate-500 text-xs italic">No story lifecycle distribution data</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={lifecycleData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={70}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {lifecycleData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <ChartTooltip />
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
      </div>

      {/* System Alerts */}
      <div className="glass rounded-2xl p-5">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">Recent System Alerts</h2>
        {!metrics?.alerts || metrics.alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 space-y-2">
            <ShieldAlert className="w-8 h-8 text-emerald-500" />
            <p className="text-xs text-slate-400">All systems green. No active warnings or alarms.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {metrics.alerts.slice(0, 5).map((alert: any, idx: number) => (
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
  );
}
