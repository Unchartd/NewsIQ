"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { Layers, Search, ArrowUpRight, ExternalLink } from "lucide-react";
import Link from "next/link";

interface Story {
  id: string;
  canonical_headline: string;
  summary: string;
  article_count: number;
  created_at: string;
  cluster_confidence: number;
}

export default function StoriesPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data, isLoading } = useQuery<{ stories: Story[]; total: number }>({
    queryKey: ["admin-stories", search, page],
    queryFn: async () => {
      const res = await apiClient.get("/admin/stories", {
        params: { q: search || undefined, skip: (page - 1) * limit, limit },
      });
      return Array.isArray(res.data)
        ? { stories: res.data, total: res.data.length }
        : res.data;
    },
  });

  const stories = data?.stories ?? (Array.isArray(data) ? (data as unknown as Story[]) : []);
  const total = data?.total ?? stories.length;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Layers className="w-6 h-6 text-primary" />
            Story Clusters
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Browse and inspect all clustered news stories
          </p>
        </div>
        <span className="text-xs text-slate-550 px-3 py-1.5 glass rounded-xl border border-border">
          {total} stories total
        </span>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          id="stories-search"
          type="text"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search stories…"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-background border border-border text-foreground text-sm placeholder-slate-650
            focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all"
        />
      </div>

      {/* Table */}
      <div className="glass rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
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
                    <td className="px-5 py-3" colSpan={5}>
                      <div className="h-3 shimmer rounded-full" />
                    </td>
                  </tr>
                ))
              ) : stories.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-slate-600">
                    No stories found.
                  </td>
                </tr>
              ) : (
                stories.map((story) => (
                  <tr
                    key={story.id}
                    className="border-b border-border/50 hover:bg-white/2 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <p className="font-medium text-slate-200 line-clamp-1">
                        {story.canonical_headline ?? "Untitled Story"}
                      </p>
                      {story.summary && (
                        <p className="text-[10px] text-slate-600 mt-0.5 line-clamp-1">
                          {story.summary}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-400 font-mono">
                      {story.article_count ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {story.cluster_confidence != null ? (
                        <span
                          className={`badge ${
                            story.cluster_confidence > 0.8
                              ? "badge-success"
                              : story.cluster_confidence > 0.6
                              ? "badge-warning"
                              : "badge-danger"
                          }`}
                        >
                          {(story.cluster_confidence * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500 font-mono whitespace-nowrap">
                      {story.created_at
                        ? new Date(story.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/stories/${story.id}`}
                        id={`story-inspect-${story.id}`}
                        className="flex items-center gap-1 text-primary hover:text-primary/80 transition-colors whitespace-nowrap"
                      >
                        Inspect <ArrowUpRight className="w-3 h-3" />
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
          <div className="flex items-center justify-between px-5 py-3 border-t border-border">
            <span className="text-xs text-slate-600">
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 rounded-lg text-xs glass border border-border text-slate-400 hover:text-slate-200 disabled:opacity-40 transition-all"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 rounded-lg text-xs glass border border-border text-slate-400 hover:text-slate-200 disabled:opacity-40 transition-all"
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
