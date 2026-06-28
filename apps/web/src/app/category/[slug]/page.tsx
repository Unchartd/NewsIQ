import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { buildCategoryMetadata } from "@/lib/metadata";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const name = slug.charAt(0).toUpperCase() + slug.slice(1);
  return buildCategoryMetadata(slug, name);
}

// /category/politics → /home?category=politics
// Permanent redirect keeps old inbound links working and eliminates the duplicate route.
export default async function CategoryPage({ params }: PageProps) {
  const { slug } = await params;
  redirect(`/home?category=${encodeURIComponent(slug)}`);
}
