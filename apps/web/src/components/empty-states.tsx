"use client";

import { motion } from "framer-motion";
import { Inbox, SearchX, ServerCrash, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EMPTY_STATE_MIN_HEIGHT } from "@/lib/layout-constants";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center justify-center px-4 text-center"
      style={{ minHeight: EMPTY_STATE_MIN_HEIGHT, width: "100%" }}
    >
      <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-4">
        <Icon className="w-7 h-7 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm mb-4">
          {description}
        </p>
      )}
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="outline" size="sm">
          {actionLabel}
        </Button>
      )}
    </motion.div>
  );
}

export function NoResults() {
  return (
    <EmptyState
      icon={SearchX}
      title="No results found"
      description="Try adjusting your search terms or filters."
    />
  );
}

export function ErrorState({
  message = "Something went wrong.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <EmptyState
      icon={ServerCrash}
      title="Error"
      description={message}
      actionLabel={onRetry ? "Try Again" : undefined}
      onAction={onRetry}
    />
  );
}
