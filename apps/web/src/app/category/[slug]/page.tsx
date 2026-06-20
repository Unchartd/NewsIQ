import type { Metadata } from "next";
import { buildCategoryMetadata } from "@/lib/metadata";
import { buildCollectionPageSchema, buildBreadcrumbSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";
import CategoryClientPage from "./category-client";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const name = slug.charAt(0).toUpperCase() + slug.slice(1);
  return buildCategoryMetadata(slug, name);
}

export default async function CategoryPage({ params }: PageProps) {
  const { slug } = await params;
  const name = slug.charAt(0).toUpperCase() + slug.slice(1);
  const url = `${SITE_URL}/category/${slug}`;

  const collectionSchema = buildCollectionPageSchema(
    `${name} News — NewsIQ`,
    `Latest ${name} news AI-summarized from multiple sources. Updated every 5 minutes.`,
    url
  );
  const breadcrumbSchema = buildBreadcrumbSchema([
    { name: "Home", url: SITE_URL },
    { name: "Categories", url: `${SITE_URL}/topics` },
    { name: `${name} News`, url },
  ]);

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(collectionSchema) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbSchema) }} />
      <CategoryClientPage slug={slug} />
    </>
  );
}

