"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend 
} from "recharts";
import { 
  DollarSign, Activity, Cpu, Sparkles, RefreshCw, TrendingUp, AlertTriangle 
} from "lucide-react";
import apiClient from "@/lib/api-client";

interface CostSummaryItem {
  provider: string;
  model: string;
  stage: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

interface CostAnalyticsResponse {
  total_cost_usd: number;
  breakdown: CostSummaryItem[];
}

const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8", "#82ca9d"];

export default function CostsPage() {
  // 1. Fetch cost analytics from backend
  const { data, isLoading, refetch } = useQuery<CostAnalyticsResponse>({
    queryKey: ["admin-costs"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/costs");
      return res.data;
    },
  });

  const breakdown = data?.breakdown || [];
  const totalCost = data?.total_cost_usd || 0;

  // Process data for Stage Chart
  const stageDataMap: { [key: string]: number } = {};
  breakdown.forEach((item) => {
    stageDataMap[item.stage] = (stageDataMap[item.stage] || 0) + item.cost_usd;
  });
  const stageChartData = Object.keys(stageDataMap).map((stage) => ({
    name: stage.replace(/_/g, " "),
    cost: roundToDecimals(stageDataMap[stage], 4),
  })).sort((a, b) => b.cost - a.cost);

  // Process data for Model Pie Chart
  const modelDataMap: { [key: string]: number } = {};
  breakdown.forEach((item) => {
    modelDataMap[item.model] = (modelDataMap[item.model] || 0) + item.cost_usd;
  });
  const modelChartData = Object.keys(modelDataMap).map((model) => ({
    name: model,
    value: roundToDecimals(modelDataMap[model], 4),
  })).sort((a, b) => b.value - a.value);

  // Helper function to round decimals
  function roundToDecimals(num: number, decimals: number): number {
    const factor = Math.pow(10, decimals);
    return Math.round(num * factor) / factor;
  }

  // Calculate high level stats
  const totalInputTokens = breakdown.reduce((sum, item) => sum + item.input_tokens, 0);
  const totalOutputTokens = breakdown.reduce((sum, item) => sum + item.output_tokens, 0);
  const avgCostPerCall = totalCost / (breakdown.length || 1);

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex justify-between items-center bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-400" />
            LLM Token & Cost Analytics
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Real-time billing telemetry and usage metrics by model, provider, and pipeline stage.
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Accumulated Cost</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-400">
              ${totalCost.toFixed(4)}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Avg Cost per Execution</CardDescription>
            <CardTitle className="text-2xl font-bold">
              ${avgCostPerCall.toFixed(4)}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Input Tokens Ingested</CardDescription>
            <CardTitle className="text-2xl font-bold font-mono">
              {totalInputTokens.toLocaleString()}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Output Tokens Generated</CardDescription>
            <CardTitle className="text-2xl font-bold font-mono">
              {totalOutputTokens.toLocaleString()}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Recharts Visualizations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Cost by stage chart */}
        <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl p-6">
          <CardHeader className="px-0 pt-0">
            <CardTitle className="text-base font-semibold">Stage Latency / Cost Distribution</CardTitle>
            <CardDescription>Dollar cost allocation per pipeline step.</CardDescription>
          </CardHeader>
          <div className="h-[300px] mt-4">
            {isLoading ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                Loading stage distribution chart...
              </div>
            ) : stageChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                No telemetry recorded yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stageChartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis type="number" stroke="#888888" fontSize={11} tickFormatter={(v) => `$${v}`} />
                  <YAxis dataKey="name" type="category" stroke="#888888" fontSize={10} width={120} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "rgba(15,23,42,0.9)", borderColor: "rgba(255,255,255,0.1)" }}
                    labelStyle={{ color: "#ffffff", fontWeight: "bold" }}
                    formatter={(v) => [`$${Number(v).toFixed(4)}`, "Cost (USD)"]}
                  />
                  <Bar dataKey="cost" fill="#0088FE" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Cost by Model pie chart */}
        <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl p-6">
          <CardHeader className="px-0 pt-0">
            <CardTitle className="text-base font-semibold">Model Spend Allocation</CardTitle>
            <CardDescription>Distribution of spend across foundation models.</CardDescription>
          </CardHeader>
          <div className="h-[300px] mt-4 flex items-center justify-center">
            {isLoading ? (
              <div className="text-xs text-muted-foreground">Loading model share chart...</div>
            ) : modelChartData.length === 0 ? (
              <div className="text-xs text-muted-foreground">No spend logged.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={modelChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {modelChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: "rgba(15,23,42,0.9)", borderColor: "rgba(255,255,255,0.1)" }}
                    formatter={(v) => [`$${Number(v).toFixed(4)}`, "Spend"]}
                  />
                  <Legend 
                    formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {/* Raw breakdown table */}
      <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden">
        <CardHeader className="border-b border-border/30">
          <CardTitle className="text-base font-semibold">Billing Details</CardTitle>
          <CardDescription>Granular breakdown of LLM operations.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/10">
              <TableRow>
                <TableHead className="text-xs">Stage</TableHead>
                <TableHead className="text-xs">Model</TableHead>
                <TableHead className="text-xs">Provider</TableHead>
                <TableHead className="text-xs text-right">Input Tokens</TableHead>
                <TableHead className="text-xs text-right">Output Tokens</TableHead>
                <TableHead className="text-xs text-right">Cost (USD)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-xs text-muted-foreground">
                    Loading data grid...
                  </TableCell>
                </TableRow>
              ) : breakdown.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-xs text-muted-foreground">
                    No cost records generated yet.
                  </TableCell>
                </TableRow>
              ) : (
                breakdown.map((item, idx) => (
                  <TableRow key={idx} className="hover:bg-muted/5">
                    <TableCell className="font-medium capitalize py-3.5 text-xs">
                      {item.stage.replace(/_/g, " ")}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{item.model}</TableCell>
                    <TableCell className="capitalize text-xs">{item.provider}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{item.input_tokens.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-xs">{item.output_tokens.toLocaleString()}</TableCell>
                    <TableCell className="text-right font-mono text-emerald-400 font-semibold text-xs">
                      ${item.cost_usd.toFixed(6)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
