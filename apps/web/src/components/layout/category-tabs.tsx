"use client";

interface CategoryTabsProps {
  categories: { slug: string; name: string }[];
  activeCategory: string;
  onSelect: (slug: string) => void;
}

export function CategoryTabs({ categories, activeCategory, onSelect }: CategoryTabsProps) {
  return (
    <div className="ctabs-wrap">
      <div className="ctabs">
        {categories.map((cat) => (
          <button
            key={cat.slug}
            className={`ctab ${activeCategory === cat.slug ? "on" : ""}`}
            onClick={() => onSelect(cat.slug)}
          >
            {cat.name}
          </button>
        ))}
      </div>
    </div>
  );
}
