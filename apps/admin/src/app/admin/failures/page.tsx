"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import apiClient from "@/lib/api-client";
import { AlertOctagon, Search, ArrowRight, Eye, RefreshCw, CheckCircle2 } from "lucide-react";

interface FailureItem {
  failureId: string;
  traceId: string | null;
  stage: string;
  provider: string | null;
  model: string | null;
  status: string;
  exception: string;
  errorCategory: string;
  errorCode: string | null;
  retryCount: number;
  latency: number;
  timestamp: string;
  resolved: boolean;
}

interface FailuresResponse {
  failures: FailureItem[];
  total: number;
}

export default function FailureCenterPage() {
  const [stageFilter, setStageFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [resolvedFilter, setResolvedFilter] = useState<string>("false"); // Default to unresolved
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const limit = 15;

  const { data, isLoading, refetch } = useQuery<FailuresResponse>({
    queryKey: ["admin-failures", stageFilter, categoryFilter, resolvedFilter, page],
    queryFn: async () => {
      const params: Record<string, string> = {
        limit: limit.toString(),
        offset: ((page - 1) * limit).toString(),
      };
      if (stageFilter) params.stage = stageFilter;
      if (categoryFilter) params.category = categoryFilter;
      if (resolvedFilter !== "all") params.resolved = resolvedFilter;
      
      const res = await apiClient.get("/admin/failures", { params });
      return res.data;
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  const failuresList = data?.failures ?? [];
  const totalCount = data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / limit);

  // Filtered client side for search query in exception/IDs
  const displayedFailures = searchQuery
    ? failuresList.filter(
        (f) =>
          f.exception.toLowerCase().includes(searchQuery.toLowerCase()) ||
          f.failureId.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (f.traceId && f.traceId.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : failuresList;

  const categories = [
    { value: "system_error", label: "System Error" },
    { value: "llm_error", label: "LLM Error" },
    { value: "data_error", label: "Data Error" },
    { value: "agent_error", label: "Agent Error" },
  ];

  const stages = [
    "ingestion_rss",
    "ingestion_gnews",
    "embedding",
    "event_extraction",
    "entity_linking",
    "clustering_batch",
    "summary_generation",
    "summary_reflection",
    "contradiction_detection",
    "judge_arbitration",
  ];

  const getCategoryStyles = (cat: string) => {
    switch (cat) {
      case "system_error":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "llm_error":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      case "data_error":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      case "agent_error":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/20";
    }
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <AlertOctagon className="w-6 h-6 text-red-500" />
            Failure Center
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time pipeline diagnostics, error tracking, and stage replays.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 self-start transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Feed
        </button>
      </div>

      {/* Filters Panel */}
      <div className="glass rounded-2xl p-5 grid grid-cols-1 sm:grid-cols-4 gap-4">
        {/* Search */}
        <div className="relative">
          <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
            <Search className="w-4 h-4" />
          </span>
          <input
            type="text"
            placeholder="Search exceptions or IDs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-primary/55 text-slate-100 placeholder-slate-500"
          />
        </div>

        {/* Category Filter */}
        <select
          value={categoryFilter}
          onChange={(e) => {
            setCategoryFilter(e.target.value);
            setPage(1);
          }}
          className="w-full px-3.5 py-2 text-sm bg-card border border-white/10 rounded-xl focus:outline-none text-slate-300"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>

        {/* Stage Filter */}
        <select
          value={stageFilter}
          onChange={(e) => {
            setStageFilter(e.target.value);
            setPage(1);
          }}
          className="w-full px-3.5 py-2 text-sm bg-card border border-white/10 rounded-xl focus:outline-none text-slate-300"
        >
          <option value="">All Stages</option>
          {stages.map((s) => (
            <option key={s} value={s}>
              {s.replace("_", " ").toUpperCase()}
            </option>
          ))}
        </select>

        {/* Resolved status Filter */}
        <select
          value={resolvedFilter}
          onChange={(e) => {
            setResolvedFilter(e.target.value);
            setPage(1);
          }}
          className="w-full px-3.5 py-2 text-sm bg-card border border-white/10 rounded-xl focus:outline-none text-slate-300"
        >
          <option value="false">Unresolved Only</option>
          <option value="true">Resolved Only</option>
          <option value="all">All Failures</option>
        </select>
      </div>

      {/* Failures Grid */}
      <div className="glass rounded-2xl overflow-hidden border border-white/5">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-white/2 text-slate-500 font-semibold uppercase tracking-wider">
                <th className="py-4 px-5">Timestamp</th>
                <th className="py-4 px-4">Stage</th>
                <th className="py-4 px-4">Category / Code</th>
                <th className="py-4 px-4">Error Exception</th>
                <th className="py-4 px-4">Provider / Model</th>
                <th className="py-4 px-4 text-center">Status</th>
                <th className="py-4 px-5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-medium">
                    <div className="flex justify-center items-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-primary" />
                      Loading pipeline logs...
                    </div>
                  </td>
                </tr>
              ) : displayedFailures.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-medium">
                    No matching pipeline failures found.
                  </td>
                </tr>
              ) : (
                displayedFailures.map((failure) => (
                  <tr
                    key={failure.failureId}
                    className="hover:bg-white/2 transition-colors duration-150"
                  >
                    <td className="py-4 px-5 font-mono text-slate-400 whitespace-nowrap">
                      {new Date(failure.timestamp).toLocaleString()}
                    </td>
                    <td className="py-4 px-4 font-semibold text-slate-200 capitalize whitespace-nowrap">
                      {failure.stage.replace("_", " ")}
                    </td>
                    <td className="py-4 px-4 whitespace-nowrap">
                      <div className="flex flex-col gap-1.5">
                        <span
                          className={`px-2 py-0.5 text-[10px] rounded-full border ${getCategoryStyles(
                            failure.errorCategory
                          )} font-semibold`}
                        >
                          {failure.errorCategory.replace("_", " ")}
                        </span>
                        {failure.errorCode && (
                          <span className="text-[10px] font-mono text-slate-500">
                            {failure.errorCode}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-4 max-w-xs sm:max-w-md">
                      <div className="text-slate-300 font-medium truncate font-mono" title={failure.exception}>
                        {failure.exception}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                        ID: {failure.failureId}
                      </div>
                    </td>
                    <td className="py-4 px-4 font-mono text-slate-400 whitespace-nowrap">
                      {failure.provider ? (
                        <div className="flex flex-col">
                          <span className="capitalize font-semibold text-slate-300">
                            {failure.provider}
                          </span>
                          <span className="text-[10px] text-slate-500">
                            {failure.model}
                          </span>
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="py-4 px-4 text-center whitespace-nowrap">
                      {failure.resolved ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3 h-3" /> Resolved
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
                          Unresolved
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-5 text-right whitespace-nowrap">
                      <Link
                        href={`/admin/failures/${failure.failureId}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-primary/10 border border-primary/20 text-primary text-xs font-semibold hover:bg-primary/20 transition-all"
                      >
                        Inspect <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-5 py-4 border-t border-white/5 bg-white/2 flex items-center justify-between">
            <span className="text-slate-500 text-xs">
              Showing page {page} of {totalPages} ({totalCount} total errors)
            </span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 rounded-xl border border-white/10 hover:bg-white/5 disabled:opacity-40 disabled:hover:bg-transparent text-xs font-semibold text-slate-300"
              >
                Previous
              </button>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 rounded-xl border border-white/10 hover:bg-white/5 disabled:opacity-40 disabled:hover:bg-transparent text-xs font-semibold text-slate-300"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
