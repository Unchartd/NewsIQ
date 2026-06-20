"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { Users, Search, ExternalLink, Edit2, Check, X } from "lucide-react";
import { toast } from "sonner";

interface Entity {
  id: string;
  name: string;
  type: string;
  wikidata_id?: string;
  confidence: number;
  mention_count: number;
}

export default function EntitiesPage() {
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [wikidataInput, setWikidataInput] = useState("");

  const { data, isLoading, refetch } = useQuery<{ entities: Entity[]; total: number }>({
    queryKey: ["admin-entities", search],
    queryFn: async () => {
      const res = await apiClient.get("/admin/entities", { params: { q: search || undefined, limit: 50 } });
      return Array.isArray(res.data) ? { entities: res.data, total: res.data.length } : res.data;
    },
  });

  const overrideMutation = useMutation({
    mutationFn: async ({ entityId, wikidataId }: { entityId: string; wikidataId: string }) => {
      await apiClient.patch(`/admin/entities/${entityId}`, { wikidata_id: wikidataId });
    },
    onSuccess: () => {
      toast.success("Wikidata ID updated!");
      setEditingId(null);
      refetch();
    },
    onError: () => toast.error("Failed to update entity."),
  });

  const entities = data?.entities ?? (Array.isArray(data) ? (data as unknown as Entity[]) : []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Users className="w-6 h-6 text-blue-400" />
          Entity Debugger
        </h1>
        <p className="text-slate-500 text-sm mt-1">Inspect and correct NER entity resolutions</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          id="entities-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search entities by name…"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[#1a1f2e] border border-[#1e2333] text-slate-200 text-sm placeholder-slate-600 focus:outline-none focus:border-indigo-500/60 transition-all"
        />
      </div>

      <div className="glass rounded-2xl overflow-hidden">
        <table className="w-full text-xs">
          <thead className="border-b border-[#1e2333]">
            <tr>
              <th className="text-left px-5 py-3 text-slate-500 font-semibold">Entity Name</th>
              <th className="text-left px-4 py-3 text-slate-500 font-semibold">Type</th>
              <th className="text-left px-4 py-3 text-slate-500 font-semibold">Wikidata ID</th>
              <th className="text-right px-4 py-3 text-slate-500 font-semibold">Mentions</th>
              <th className="text-right px-4 py-3 text-slate-500 font-semibold">Confidence</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} className="border-b border-[#1e2333]/50">
                  <td colSpan={6} className="px-5 py-3">
                    <div className="h-3 shimmer rounded-full" />
                  </td>
                </tr>
              ))
            ) : entities.length === 0 ? (
              <tr><td colSpan={6} className="px-5 py-12 text-center text-slate-600">No entities found.</td></tr>
            ) : (
              entities.map((entity) => (
                <tr key={entity.id} className="border-b border-[#1e2333]/50 hover:bg-white/2 transition-colors">
                  <td className="px-5 py-3 font-medium text-slate-200">{entity.name}</td>
                  <td className="px-4 py-3"><span className="badge badge-neutral">{entity.type}</span></td>
                  <td className="px-4 py-3">
                    {editingId === entity.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={wikidataInput}
                          onChange={(e) => setWikidataInput(e.target.value)}
                          placeholder="Q12345"
                          autoFocus
                          className="w-24 px-2 py-1 rounded-lg bg-[#1a1f2e] border border-indigo-500/60 text-slate-200 text-xs font-mono focus:outline-none"
                        />
                        <button
                          onClick={() => overrideMutation.mutate({ entityId: entity.id, wikidataId: wikidataInput })}
                          className="text-emerald-400 hover:text-emerald-300"
                        ><Check className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setEditingId(null)} className="text-slate-500 hover:text-slate-300">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : entity.wikidata_id ? (
                      <a href={`https://www.wikidata.org/wiki/${entity.wikidata_id}`} target="_blank" rel="noopener noreferrer"
                        className="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-mono">
                        {entity.wikidata_id} <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="text-slate-600 italic">Not resolved</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-400">{entity.mention_count ?? "—"}</td>
                  <td className="px-4 py-3 text-right font-mono text-slate-400">
                    {entity.confidence != null ? `${(entity.confidence * 100).toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      id={`edit-entity-${entity.id}`}
                      onClick={() => { setEditingId(entity.id); setWikidataInput(entity.wikidata_id ?? ""); }}
                      className="text-slate-500 hover:text-indigo-400 transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
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
