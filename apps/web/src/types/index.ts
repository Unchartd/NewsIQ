/**
 * TypeScript types mirroring backend Pydantic schemas / DB models.
 * These types are used throughout the frontend for type safety.
 */

// ──────────────────────────────────────────────
// User & Auth
// ──────────────────────────────────────────────

export type UserRole = "guest" | "user" | "premium" | "admin";
export type SubscriptionPlan = "free" | "pro" | "enterprise";
export type SummaryType = "one_line" | "short" | "detailed";

export interface User {
  id: string;
  email: string;
  name: string | null;
  image_url: string | null;
  role: UserRole;
  subscription_plan: SubscriptionPlan;
  status: string;
  created_at: string;
}

export interface UserPreferences {
  preferred_summary_type: SummaryType;
  theme: "light" | "dark" | "system";
  language: string;
  categories: string[]; // category slugs
  countries: string[];
  cities: string[];
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ──────────────────────────────────────────────
// Content: Categories, Sources
// ──────────────────────────────────────────────

export interface Category {
  id: string;
  slug: string;
  name: string;
  icon: string | null;
}

export interface Source {
  id: string;
  name: string;
  slug: string;
  website_url: string | null;
  logo_url: string | null;
  country_code: string | null;
}

// ──────────────────────────────────────────────
// Articles
// ──────────────────────────────────────────────

export interface Article {
  id: string;
  source: Source;
  title: string;
  description: string | null;
  url: string;
  author: string | null;
  image_url: string | null;
  published_at: string;
}

// ──────────────────────────────────────────────
// Stories
// ──────────────────────────────────────────────

export interface Story {
  id: string;
  headline: string;
  one_line_summary: string;
  short_summary: string;
  detailed_summary: string;
  category: Category | null;
  location_country: string | null;
  location_state: string | null;
  location_city: string | null;
  trend_score: number;
  story_status: string;
  first_seen_at: string;
  updated_at: string;
  article_count: number;
  source_count: number;
  tags: string[];
}

export interface StoryDetail extends Story {
  articles: Article[];
  timeline: TimelineEvent[];
  entities: StoryEntity[];
  source_coverage: SourceCoverage[];
  differences: StoryDifference[];
  metrics: StoryMetrics;
  related_stories: Story[];
}

export interface TimelineEvent {
  id: string;
  event_time: string;
  description: string;
}

export interface StoryEntity {
  id: string;
  entity_type: "PERSON" | "ORG" | "LOCATION" | "EVENT" | "COUNTRY";
  entity_value: string;
}

export interface SourceCoverage {
  id: string;
  source: Source;
  focus_area: string;
  published_at: string;
}

export interface StoryDifference {
  id: string;
  source: Source;
  unique_information: string | null;
  missing_information: string | null;
  contradictions: string | null;
}

export interface StoryMetrics {
  views: number;
  bookmarks: number;
  shares: number;
  clicks: number;
}

// ──────────────────────────────────────────────
// API Responses
// ──────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface SearchResult {
  stories: Story[];
  total: number;
  query: string;
}

export interface TrendingResponse {
  stories: Story[];
  period: "today" | "24h" | "7d" | "30d";
}

// ──────────────────────────────────────────────
// Notifications
// ──────────────────────────────────────────────

export interface Notification {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

// ──────────────────────────────────────────────
// Bookmarks
// ──────────────────────────────────────────────

export interface Bookmark {
  story: Story;
  created_at: string;
}
