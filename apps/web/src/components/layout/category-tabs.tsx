"use client";

interface CategoryTabsProps {
  categories: { slug: string; name: string }[];
  activeCategory: string;
  onSelect: (slug: string) => void;
}

export function CategoryTabs({ categories, activeCategory, onSelect }: CategoryTabsProps) {
  return (
    <div className="niq-cat-tabs-wrap">
      <div className="niq-cat-tabs">
        {categories.map((cat) => (
          <button
            key={cat.slug}
            className={`niq-cat-tab ${activeCategory === cat.slug ? "active" : ""}`}
            onClick={() => onSelect(cat.slug)}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
