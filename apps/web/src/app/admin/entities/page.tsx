"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { 
  Users, Search, Filter, ExternalLink, RefreshCw, CheckCircle, 
  AlertCircle, Edit2, Link2 
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { toast } from "sonner";

interface EntityDebuggerItem {
  id: string;
  name: string;
  type: string;
  confidence: number;
  wikidata_id: string | null;
  occurrences: number;
}

interface EntityDebuggerResponse {
  entities: EntityDebuggerItem[];
}

export default function EntitiesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedType, setSelectedType] = useState<string>("all");
  
  // Correction modal states
  const [editingEntity, setEditingEntity] = useState<EntityDebuggerItem | null>(null);
  const [wikidataId, setWikidataId] = useState("");
  const [notes, setNotes] = useState("");

  // 1. Fetch entity debugger data
  const { data, isLoading, refetch } = useQuery<EntityDebuggerResponse>({
    queryKey: ["admin-entities"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/entities");
      return res.data;
    },
  });

  const entities = data?.entities || [];

  // Filter entities
  const filteredEntities = entities.filter((ent) => {
    const matchesSearch = ent.name.toLowerCase().includes(search.toLowerCase()) || 
      (ent.wikidata_id && ent.wikidata_id.toLowerCase().includes(search.toLowerCase()));
    const matchesType = selectedType === "all" || ent.type === selectedType;
    return matchesSearch && matchesType;
  });

  // Unique entity types
  const types = Array.from(new Set(entities.map((e) => e.type)));

  // Correction mutation
  const correctEntityMutation = useMutation({
    mutationFn: async (payload: { entityName: string; wikidataId: string; notes: string }) => {
      // Log the correction action. We use a placeholder storyId (e.g. all-zeros UUID or empty) 
      // since this is a global entity override rather than a single story.
      const nilUuid = "00000000-0000-0000-0000-000000000000";
      await apiClient.post(`/admin/review/${nilUuid}/action`, {
        action: "correct_entity",
        target_type: "entity",
        target_id: editingEntity?.id,
        before_value: { name: editingEntity?.name, wikidata_id: editingEntity?.wikidata_id },
        after_value: { name: editingEntity?.name, wikidata_id: payload.wikidataId },
        notes: payload.notes,
      });
    },
    onSuccess: () => {
      toast.success("Entity correction successfully queued in audit trail.");
      setEditingEntity(null);
      setWikidataId("");
      setNotes("");
      queryClient.invalidateQueries({ queryKey: ["admin-entities"] });
    },
    onError: () => {
      toast.error("Failed to submit entity correction.");
    }
  });

  const handleOpenEdit = (ent: EntityDebuggerItem) => {
    setEditingEntity(ent);
    setWikidataId(ent.wikidata_id || "");
    setNotes("");
  };

  const handleSaveCorrection = () => {
    if (!editingEntity) return;
    correctEntityMutation.mutate({
      entityName: editingEntity.name,
      wikidataId: wikidataId.trim(),
      notes: notes.trim(),
    });
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex justify-between items-center bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            Entity Canonicalization Panel
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Debug Named Entity Recognition confidence levels and Wikidata resolution mappings.
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Filter and Search controls */}
      <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl p-4 flex flex-col sm:flex-row gap-4 items-center">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search entity name or Wikidata ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 rounded-xl text-xs h-9 bg-background/50 border-border/40"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 justify-end">
          <Filter className="w-4 h-4 text-muted-foreground" />
          <div className="flex gap-1.5 overflow-x-auto">
            <Button
              variant={selectedType === "all" ? "default" : "outline"}
              onClick={() => setSelectedType("all")}
              className="rounded-xl text-[10px] h-7 px-3"
            >
              All Types
            </Button>
            {types.map((type) => (
              <Button
                key={type}
                variant={selectedType === type ? "default" : "outline"}
                onClick={() => setSelectedType(type)}
                className="rounded-xl text-[10px] h-7 px-3 uppercase"
              >
                {type}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {/* Entities Table */}
      <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader className="bg-muted/10">
              <TableRow>
                <TableHead className="text-xs">Entity Name</TableHead>
                <TableHead className="text-xs">Type</TableHead>
                <TableHead className="text-xs text-center">Confidence</TableHead>
                <TableHead className="text-xs">Wikidata ID</TableHead>
                <TableHead className="text-xs text-right">Occurrences</TableHead>
                <TableHead className="text-xs text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-xs text-muted-foreground">
                    Resolving entities list...
                  </TableCell>
                </TableRow>
              ) : filteredEntities.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-xs text-muted-foreground">
                    No entities match the query parameters.
                  </TableCell>
                </TableRow>
              ) : (
                filteredEntities.map((ent) => (
                  <TableRow key={ent.id} className="hover:bg-muted/5">
                    <TableCell className="font-bold py-3.5 text-xs text-foreground">
                      {ent.name}
                    </TableCell>
                    <TableCell className="py-3.5 text-xs">
                      <Badge variant="outline" className="uppercase font-mono text-[9px] py-0">
                        {ent.type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center py-3.5 text-xs">
                      <div className="flex items-center justify-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${
                          ent.confidence >= 0.9 
                            ? "bg-emerald-500" 
                            : ent.confidence >= 0.7 
                            ? "bg-amber-500" 
                            : "bg-rose-500"
                        }`} />
                        <span className="font-mono">{ent.confidence.toFixed(2)}</span>
                      </div>
                    </TableCell>
                    <TableCell className="py-3.5 text-xs">
                      {ent.wikidata_id ? (
                        <a
                          href={`https://www.wikidata.org/wiki/${ent.wikidata_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline flex items-center gap-1 font-mono text-xs"
                        >
                          {ent.wikidata_id}
                          <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground font-mono text-xs">Unlinked</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono py-3.5 text-xs text-foreground font-semibold">
                      {ent.occurrences.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right py-3.5 text-xs">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleOpenEdit(ent)}
                        className="rounded-lg text-[10px] h-7 px-2.5 flex gap-1 items-center ml-auto border-primary/20 text-primary hover:bg-primary/10"
                      >
                        <Link2 className="w-3 h-3" />
                        Map Wiki
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Map Wikidata Modal Dialog */}
      <Dialog open={!!editingEntity} onOpenChange={(open) => !open && setEditingEntity(null)}>
        <DialogContent className="rounded-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="text-base font-bold">Map Entity to Wikidata</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Provide the Wikidata Q-ID (e.g. Q76 for Barack Obama) for the resolved canonical entity.
            </DialogDescription>
          </DialogHeader>

          {editingEntity && (
            <div className="space-y-4 py-4">
              <div>
                <span className="text-[10px] font-bold text-muted-foreground uppercase">Entity Name</span>
                <p className="text-sm font-semibold text-foreground mt-0.5">{editingEntity.name}</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Wikidata Q-ID</label>
                <Input
                  placeholder="e.g. Q76"
                  value={wikidataId}
                  onChange={(e) => setWikidataId(e.target.value)}
                  className="rounded-xl text-xs h-9 bg-background/50"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Reason/Notes (Required for audit log)</label>
                <Input
                  placeholder="e.g. Linked to correct Wikidata identity profile"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="rounded-xl text-xs h-9 bg-background/50"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setEditingEntity(null)} className="rounded-xl text-xs h-9">
              Cancel
            </Button>
            <Button
              onClick={handleSaveCorrection}
              disabled={correctEntityMutation.isPending || !wikidataId.trim() || !notes.trim()}
              className="rounded-xl text-xs h-9"
            >
              Submit Override
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
