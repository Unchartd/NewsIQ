"use client";

const CATEGORY_CLASS_MAP: Record<string, string> = {
  politics: "niq-badge-politics",
  technology: "niq-badge-technology",
  tech: "niq-badge-tech",
  business: "niq-badge-business",
  sports: "niq-badge-sports",
  health: "niq-badge-health",
  science: "niq-badge-science",
  weather: "niq-badge-weather",
  world: "niq-badge-world",
  entertainment: "niq-badge-entertainment",
};

interface CategoryBadgeProps {
  category: string;
  className?: string;
}

export function CategoryBadge({ category, className = "" }: CategoryBadgeProps) {
  const slug = category.toLowerCase();
  const colorClass = CATEGORY_CLASS_MAP[slug] || "niq-badge-world";

  return (
    <span className={`niq-cat-badge ${colorClass} ${className}`}>
      {category}
    </span>
  );
}
