"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Shield, Play, Settings, Plus, RefreshCw, Layers } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { toast } from "sonner";

interface Source {
  id: string;
  name: string;
  slug: string;
  website_url: string;
  logo_url: string;
  country_code: string;
  rss_url: string;
  active: boolean;
}

export default function AdminPage() {
  const { user, isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();

  const isAdmin = user?.role === "admin";

  // Form states for new source
  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceSlug, setNewSourceSlug] = useState("");
  const [newSourceRss, setNewSourceRss] = useState("");
  const [newSourceWeb, setNewSourceWeb] = useState("");
  const [newSourceLogo, setNewSourceLogo] = useState("");
  const [newSourceCountry, setNewSourceCountry] = useState("US");

  // Load sources
  const { data: sources, isLoading, refetch } = useQuery<Source[]>({
    queryKey: ["admin-sources"],
    queryFn: async () => {
      const response = await apiClient.get("/sources", {
        params: { active_only: "false" },
      });
      return response.data;
    },
    enabled: isAuthenticated && isAdmin,
  });

  // Ingestion task trigger mutation
  const triggerIngestionMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources/trigger-ingestion");
    },
    onSuccess: () => {
      toast.success("News ingestion Celery task successfully queued!");
    },
    onError: () => {
      toast.error("Failed to queue ingestion task.");
    },
  });

  // Source creation mutation
  const createSourceMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources", {
        name: newSourceName,
        slug: newSourceSlug,
        rss_url: newSourceRss,
        website_url: newSourceWeb,
        logo_url: newSourceLogo,
        country_code: newSourceCountry,
        active: true,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sources"] });
      toast.success("News source successfully added.");
      // Clear fields
      setNewSourceName("");
      setNewSourceSlug("");
      setNewSourceRss("");
      setNewSourceWeb("");
      setNewSourceLogo("");
    },
    onError: () => {
      toast.error("Failed to create news source. Ensure slug is unique.");
    },
  });

  return (
    <div className="space-y-6">
      {/* Pipeline Control Card */}
      <Card className="border-border/50 rounded-2xl bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Play className="w-4 h-4 text-muted-foreground" />
            Pipeline Operations
          </CardTitle>
          <CardDescription>Manually trigger Celery news worker pipelines.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Button
            onClick={() => triggerIngestionMutation.mutate()}
            disabled={triggerIngestionMutation.isPending}
            className="rounded-xl flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${triggerIngestionMutation.isPending ? "animate-spin" : ""}`} />
            Trigger News Ingestion
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Add Source Form */}
        <Card className="border-border/50 rounded-2xl bg-card/50 backdrop-blur-sm h-fit">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Plus className="w-4 h-4 text-muted-foreground" />
              Add News Source
            </CardTitle>
            <CardDescription>Register a new publisher RSS feed.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Publisher Name</label>
                <Input
                  placeholder="e.g. Reuters"
                  value={newSourceName}
                  onChange={(e) => {
                    setNewSourceName(e.target.value);
                    setNewSourceSlug(e.target.value.toLowerCase().replace(/\s+/g, "-"));
                  }}
                  className="rounded-xl text-xs h-9"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Slug</label>
                <Input
                  placeholder="e.g. reuters"
                  value={newSourceSlug}
                  onChange={(e) => setNewSourceSlug(e.target.value)}
                  className="rounded-xl text-xs h-9"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">RSS Feed URL</label>
              <Input
                placeholder="https://www.reuters.com/rss"
                value={newSourceRss}
                onChange={(e) => setNewSourceRss(e.target.value)}
                className="rounded-xl text-xs h-9"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-muted-foreground">Website URL</label>
              <Input
                placeholder="https://www.reuters.com"
                value={newSourceWeb}
                onChange={(e) => setNewSourceWeb(e.target.value)}
                className="rounded-xl text-xs h-9"
              />
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2 space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Logo URL</label>
                <Input
                  placeholder="https://example.com/logo.png"
                  value={newSourceLogo}
                  onChange={(e) => setNewSourceLogo(e.target.value)}
                  className="rounded-xl text-xs h-9"
                />
              </div>
              <div className="col-span-1 space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground">Country</label>
                <Input
                  placeholder="US"
                  value={newSourceCountry}
                  onChange={(e) => setNewSourceCountry(e.target.value.toUpperCase())}
                  className="rounded-xl text-xs h-9"
                />
              </div>
            </div>
          </CardContent>
          <CardFooter className="bg-secondary/20 py-3 flex justify-end">
            <Button
              onClick={() => createSourceMutation.mutate()}
              disabled={createSourceMutation.isPending || !newSourceName || !newSourceRss}
              className="rounded-xl text-xs h-9 px-4"
            >
              Add Source
            </Button>
          </CardFooter>
        </Card>

        {/* News Sources List */}
        <Card className="border-border/50 rounded-2xl bg-card/50 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Layers className="w-4 h-4 text-muted-foreground" />
              Active Feeds
            </CardTitle>
            <CardDescription>Publishers currently active in ingestion.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[380px] overflow-y-auto space-y-3">
            {isLoading ? (
              <p className="text-xs text-muted-foreground">Loading sources...</p>
            ) : !sources || sources.length === 0 ? (
              <p className="text-xs text-muted-foreground">No sources added yet.</p>
            ) : (
              sources.map((src) => (
                <div
                  key={src.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-border/40 hover:bg-muted/10 transition-colors"
                >
                  <div>
                    <p className="text-xs font-bold text-foreground">{src.name}</p>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[240px] mt-0.5">
                      {src.rss_url}
                    </p>
                  </div>
                  <Badge variant={src.active ? "secondary" : "outline"} className="text-[9px]">
                    {src.active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
