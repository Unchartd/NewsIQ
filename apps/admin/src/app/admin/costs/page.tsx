"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { DollarSign, Zap, TrendingUp, BarChart3 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const PIE_COLORS = ["#e8334a", "#fb7185", "#be123c", "#fbbf24", "#5b8def", "#8b5cf6", "#6b6b62"];

interface CostData {
  total_cost_usd: number;
  total_tokens: number;
  by_stage: Record<string, number>;
  by_model: Record<string, number>;
}

export default function CostsPage() {
  const { data, isLoading } = useQuery<CostData>({
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

  const stageData = data?.by_stage
    ? Object.entries(data.by_stage)
        .sort(([, a], [, b]) => b - a)
        .map(([stage, cost]) => ({ stage: stage.replace("_", " "), cost: Number(cost.toFixed(6)) }))
    : [];

  const modelData = data?.by_model
    ? Object.entries(data.by_model)
        .sort(([, a], [, b]) => b - a)
        .map(([model, cost]) => ({ name: model, value: Number(cost.toFixed(6)) }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <DollarSign className="w-6 h-6 text-amber-400" />
          Cost Analytics
        </h1>
        <p className="text-slate-500 text-sm mt-1">AI model spend and token usage breakdown</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Cost", value: data ? `$${data.total_cost_usd.toFixed(4)}` : "—", icon: DollarSign, color: "text-amber-400 bg-amber-500/15" },
          { label: "Total Tokens", value: data?.total_tokens?.toLocaleString() ?? "—", icon: Zap, color: "text-primary bg-primary/15" },
          { label: "Stages Tracked", value: stageData.length || "—", icon: BarChart3, color: "text-primary bg-primary/15" },
          { label: "Models Used", value: modelData.length || "—", icon: TrendingUp, color: "text-blue-400 bg-blue-500/15" },
        ].map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="glass rounded-2xl p-5">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${c.color} mb-3`}>
                <Icon className="w-5 h-5" />
              </div>
              <p className="text-2xl font-bold text-slate-100 tabular-nums">{isLoading ? "—" : c.value}</p>
              <p className="text-xs text-slate-500 mt-1">{c.label}</p>
            </div>
          );
        })}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost by stage bar chart */}
        <div className="glass rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">Cost by Pipeline Stage</h2>
          {stageData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-500 text-sm">No data yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={stageData} layout="vertical" margin={{ left: 20, right: 20, top: 0, bottom: 0 }}>
                <XAxis type="number" dataKey="cost" tick={{ fill: "#64748b", fontSize: 10 }} tickFormatter={(v) => `$${v.toFixed(4)}`} />
                <YAxis type="category" dataKey="stage" tick={{ fill: "#94a3b8", fontSize: 10 }} width={100} />
                <Tooltip
                  contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 11 }}
                  formatter={(v: unknown) => [`$${Number(v).toFixed(6)}`, "Cost"]}
                />
                <Bar dataKey="cost" fill="#e8334a" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Cost by model pie chart */}
        <div className="glass rounded-2xl p-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-4">Cost Distribution by Model</h2>
          {modelData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-slate-500 text-sm">No data yet.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={modelData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {modelData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "var(--color-card)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 11 }}
                  formatter={(v) => [`$${Number(v).toFixed(6)}`, "Cost"]}
                />
                <Legend
                  iconSize={8}
                  iconType="circle"
                  formatter={(v) => <span style={{ color: "#94a3b8", fontSize: 10 }}>{v}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Cost breakdown table */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-slate-200">Spend Breakdown by Stage</h2>
        </div>
        <table className="w-full text-xs">
          <thead className="border-b border-border">
            <tr>
              <th className="text-left px-5 py-3 text-slate-500 font-semibold">Stage</th>
              <th className="text-right px-4 py-3 text-slate-500 font-semibold">Cost (USD)</th>
              <th className="text-right px-4 py-3 text-slate-500 font-semibold">% Total</th>
            </tr>
          </thead>
          <tbody>
            {stageData.length === 0 ? (
              <tr><td colSpan={3} className="px-5 py-8 text-center text-slate-600">No data.</td></tr>
            ) : (
              stageData.map((row) => (
                <tr key={row.stage} className="border-b border-border/50 hover:bg-white/2 transition-colors">
                  <td className="px-5 py-3 font-medium text-slate-300 capitalize">{row.stage}</td>
                  <td className="px-4 py-3 text-right font-mono text-amber-400">${row.cost.toFixed(6)}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-500">
                    {data ? ((row.cost / data.total_cost_usd) * 100).toFixed(1) : "—"}%
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
