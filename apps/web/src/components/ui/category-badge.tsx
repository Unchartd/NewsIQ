"use client";

const CATEGORY_CLASS_MAP: Record<string, string> = {
  politics: "bp",
  pol: "bp",
  technology: "bt",
  tech: "bt",
  business: "bb",
  biz: "bb",
  sports: "bs",
  spo: "bs",
  health: "bh",
  hlt: "bh",
  science: "bsc",
  sci: "bsc",
  weather: "bw",
  wea: "bw",
  world: "bwl",
  wld: "bwl",
};

interface CategoryBadgeProps {
  category: string;
  className?: string;
}

export function CategoryBadge({ category, className = "" }: CategoryBadgeProps) {
  const slug = category.toLowerCase();
  const colorClass = CATEGORY_CLASS_MAP[slug] || "bwl";

  return (
    <span className={`cbadge ${colorClass} ${className}`}>
      {category}
    </span>
  );
}
