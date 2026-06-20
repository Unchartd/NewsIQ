"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { Layers, Search, GitMerge, Scissors, ArrowUpRight } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

interface Cluster {
  id: string;
  canonical_headline: string;
  article_count: number;
  cluster_confidence: number;
  created_at: string;
}

export default function ClustersPage() {
  const [search, setSearch] = useState("");
  const [mergeTarget, setMergeTarget] = useState("");
  const [mergeSource, setMergeSource] = useState("");
  const [splitId, setSplitId] = useState("");

  const { data, isLoading } = useQuery<Cluster[]>({
    queryKey: ["admin-clusters", search],
    queryFn: async () => {
      const res = await apiClient.get("/admin/clusters", { params: { q: search || undefined, limit: 50 } });
      return Array.isArray(res.data) ? res.data : res.data?.clusters ?? [];
    },
  });

  const mergeMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/admin/clusters/merge", { source_id: mergeSource, target_id: mergeTarget });
    },
    onSuccess: () => { toast.success("Clusters merged!"); setMergeSource(""); setMergeTarget(""); },
    onError: () => toast.error("Merge failed."),
  });

  const splitMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/admin/clusters/${splitId}/split`);
    },
    onSuccess: () => { toast.success("Cluster split queued!"); setSplitId(""); },
    onError: () => toast.error("Split failed."),
  });

  const clusters = data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Layers className="w-6 h-6 text-primary" />
          Cluster Debugger
        </h1>
        <p className="text-slate-500 text-sm mt-1">Inspect story clusters and perform split/merge operations</p>
      </div>

      {/* Operations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass rounded-2xl p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <GitMerge className="w-4 h-4 text-emerald-400" />
            Merge Clusters
          </h2>
          <div className="space-y-2">
            <input value={mergeSource} onChange={(e) => setMergeSource(e.target.value)} placeholder="Source Cluster ID"
              className="w-full px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-655 focus:outline-none focus:border-primary/60 transition-all font-mono" />
            <input value={mergeTarget} onChange={(e) => setMergeTarget(e.target.value)} placeholder="Target Cluster ID"
              className="w-full px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-655 focus:outline-none focus:border-primary/60 transition-all font-mono" />
          </div>
          <button
            id="merge-clusters-btn"
            onClick={() => mergeMutation.mutate()}
            disabled={!mergeSource || !mergeTarget || mergeMutation.isPending}
            className="w-full py-2 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold hover:bg-emerald-600/30 transition-all disabled:opacity-40"
          >
            Merge →
          </button>
        </div>

        <div className="glass rounded-2xl p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Scissors className="w-4 h-4 text-amber-400" />
            Split Cluster
          </h2>
          <input value={splitId} onChange={(e) => setSplitId(e.target.value)} placeholder="Cluster ID to split"
            className="w-full px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-655 focus:outline-none focus:border-primary/60 transition-all font-mono" />
          <button
            id="split-cluster-btn"
            onClick={() => splitMutation.mutate()}
            disabled={!splitId || splitMutation.isPending}
            className="w-full py-2 rounded-xl bg-amber-600/20 border border-amber-500/30 text-amber-400 text-xs font-semibold hover:bg-amber-600/30 transition-all disabled:opacity-40"
          >
            Split ✂
          </button>
        </div>
      </div>

      {/* Search & table */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input id="clusters-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search clusters…"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-background border border-border text-slate-200 text-sm placeholder-slate-650 focus:outline-none focus:border-primary/60 transition-all" />
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        <table className="w-full text-xs">
          <thead className="border-b border-border">
            <tr>
              <th className="text-left px-5 py-3 text-slate-500 font-semibold">Headline</th>
              <th className="text-center px-4 py-3 text-slate-500 font-semibold">Articles</th>
              <th className="text-center px-4 py-3 text-slate-500 font-semibold">Confidence</th>
              <th className="text-left px-4 py-3 text-slate-500 font-semibold">Created</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td colSpan={5} className="px-5 py-3"><div className="h-3 shimmer rounded-full" /></td>
                </tr>
              ))
            ) : clusters.length === 0 ? (
              <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-600">No clusters found.</td></tr>
            ) : (
              clusters.map((c) => (
                <tr key={c.id} className="border-b border-border/50 hover:bg-white/2 transition-colors">
                  <td className="px-5 py-3">
                    <p className="font-medium text-slate-200 line-clamp-1">{c.canonical_headline ?? "Untitled"}</p>
                    <p className="text-[10px] text-slate-600 font-mono mt-0.5">{c.id}</p>
                  </td>
                  <td className="px-4 py-3 text-center font-mono text-slate-400">{c.article_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`badge ${c.cluster_confidence > 0.8 ? "badge-success" : c.cluster_confidence > 0.6 ? "badge-warning" : "badge-danger"}`}>
                      {c.cluster_confidence != null ? `${(c.cluster_confidence * 100).toFixed(0)}%` : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 font-mono whitespace-nowrap">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/dashboard/stories/${c.id}`} className="text-primary hover:text-primary/80 flex items-center gap-1 transition-colors">
                      Inspect <ArrowUpRight className="w-3 h-3" />
                    </Link>
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
