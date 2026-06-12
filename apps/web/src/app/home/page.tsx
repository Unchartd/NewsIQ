import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Home Feed",
};

export default function HomePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold">NewsIQ Home Feed</h1>
        <p className="text-muted-foreground">
          Story cards, trending banner, and infinite scroll will be built in Phase 6.
        </p>
      </div>
    </div>
  );
}
