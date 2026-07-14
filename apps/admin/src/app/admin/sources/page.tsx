"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { Radio, Plus, RefreshCw, Loader2, Play } from "lucide-react";
import { toast } from "sonner";

interface Source {
  id: string;
  name: string;
  slug: string;
  rss_url: string;
  website_url?: string;
  country_code: string;
  active: boolean;
}

export default function SourcesPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [rssUrl, setRssUrl] = useState("");
  const [webUrl, setWebUrl] = useState("");
  const [country, setCountry] = useState("US");

  const { data: sources, isLoading } = useQuery<Source[]>({
    queryKey: ["admin-sources"],
    queryFn: async () => {
      const res = await apiClient.get("/sources", { params: { active_only: "false" } });
      return res.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources", { name, slug, rss_url: rssUrl, website_url: webUrl, country_code: country, active: true });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-sources"] });
      toast.success("Source added successfully!");
      setName(""); setSlug(""); setRssUrl(""); setWebUrl("");
    },
    onError: () => toast.error("Failed to add source."),
  });

  const triggerMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/admin/pipeline/trigger");
      return res.data;
    },
    onSuccess: () => toast.success("Pipeline triggered — ingest + cluster queued!"),
    onError: (err: any) => {
      if (err.response?.status === 409) {
        toast.warning("Pipeline is paused. Resume it first or use Force Trigger on the Pipeline page.");
      } else {
        toast.error("Failed to trigger pipeline.");
      }
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Radio className="w-6 h-6 text-primary" />
            News Sources
          </h1>
          <p className="text-slate-500 text-sm mt-1">Manage RSS feeds and trigger ingestion</p>
        </div>
        <button
          id="trigger-ingestion-btn"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold transition-all shadow-lg shadow-primary/20 disabled:opacity-50"
        >
          {triggerMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          Trigger Ingestion
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Add source form */}
        <div className="glass rounded-2xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <Plus className="w-4 h-4 text-primary" />
            Add News Source
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Publisher Name", val: name, set: (v: string) => { setName(v); setSlug(v.toLowerCase().replace(/\s+/g, "-")); }, ph: "Reuters" },
              { label: "Slug", val: slug, set: setSlug, ph: "reuters" },
            ].map((f) => (
              <div key={f.label} className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{f.label}</label>
                <input value={f.val} onChange={(e) => f.set(e.target.value)} placeholder={f.ph}
                  className="w-full px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-650 focus:outline-none focus:border-primary/60 transition-all" />
              </div>
            ))}
          </div>
          {[
            { label: "RSS Feed URL", val: rssUrl, set: setRssUrl, ph: "https://rss.example.com/feed" },
            { label: "Website URL", val: webUrl, set: setWebUrl, ph: "https://example.com" },
          ].map((f) => (
            <div key={f.label} className="space-y-1.5">
              <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{f.label}</label>
              <input value={f.val} onChange={(e) => f.set(e.target.value)} placeholder={f.ph}
                className="w-full px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-655 focus:outline-none focus:border-primary/60 transition-all" />
            </div>
          ))}
          <div className="space-y-1.5">
            <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Country Code</label>
            <input value={country} onChange={(e) => setCountry(e.target.value.toUpperCase().slice(0, 2))} placeholder="US"
              className="w-24 px-3 py-2 rounded-xl bg-background border border-border text-slate-200 text-xs placeholder-slate-655 focus:outline-none focus:border-primary/60 transition-all" />
          </div>
          <button
            id="add-source-btn"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !name || !rssUrl}
            className="w-full py-2.5 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {createMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Add Source
          </button>
        </div>

        {/* Sources list */}
        <div className="glass rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-border flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">Active Feeds</h2>
            <span className="text-xs text-slate-500 font-mono">{sources?.length ?? 0} sources</span>
          </div>
          <div className="overflow-y-auto max-h-[480px]">
            {isLoading ? (
              <div className="p-5 space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-10 shimmer rounded-xl" />
                ))}
              </div>
            ) : (sources ?? []).length === 0 ? (
              <div className="py-12 text-center text-slate-600 text-sm">No sources added yet.</div>
            ) : (
              sources!.map((src) => (
                <div key={src.id} className="flex items-center gap-3 px-5 py-3 border-b border-border/50 hover:bg-white/2 transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-200">{src.name}</p>
                    <p className="text-[10px] text-slate-600 truncate mt-0.5">{src.rss_url}</p>
                  </div>
                  <span className={`badge ${src.active ? "badge-success" : "badge-neutral"}`}>
                    {src.active ? "Active" : "Inactive"}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
