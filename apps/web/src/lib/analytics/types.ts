/**
 * Strongly typed definitions for unified analytics events and properties.
 */

export interface CustomDimensions {
  story_category?: string;
  story_id?: string;
  story_cluster_id?: string;
  news_source?: string;
  publisher?: string;
  country?: string;
  language?: string;
  reading_time?: number;
  summary_type?: "one_line" | "short" | "detailed";
  ai_feature?: string;
  user_tier?: "guest" | "user" | "premium" | "admin";
  subscription_status?: "free" | "pro" | "enterprise";
  device_type?: string;
  theme?: "light" | "dark" | "system";
  referral_source?: string;
  experiment_id?: string;
  version?: string;
}

export interface UserTraits {
  user_tier: "guest" | "user" | "premium" | "admin";
  subscription_status: "free" | "pro" | "enterprise";
  created_at?: string;
  preferred_language?: string;
}

export type EventName =
  // User Lifecycle
  | "user_signup"
  | "user_login"
  | "logout"
  | "session_start"
  | "session_end"
  
  // Stories
  | "story_view"
  | "story_open"
  | "story_scroll"
  | "story_complete"
  | "story_share"
  | "story_bookmark"
  | "story_copy_link"
  | "story_reaction"
  | "story_read_time"
  
  // AI Interactions
  | "summary_view"
  | "summary_expand"
  | "source_comparison_open"
  | "difference_engine_open"
  | "timeline_open"
  | "key_facts_view"
  | "fact_check_view"
  | "translation_used"
  | "audio_summary_play"
  | "citation_click"
  | "ai_retry"
  | "ai_failure"
  
  // Search
  | "search_started"
  | "search_completed"
  | "search_result_click"
  | "search_no_results"
  | "search_filter_applied"
  | "search_sort_changed"
  
  // Personalization
  | "topic_follow"
  | "topic_unfollow"
  | "feed_refresh"
  | "recommendation_clicked"
  | "notification_enabled"
  | "notification_clicked"
  
  // Navigation
  | "page_view"
  | "route_change"
  | "menu_open"
  | "menu_close"
  | "footer_click"
  | "header_click"
  
  // Engagement
  | "session_duration"
  | "engaged_session"
  
  // Errors
  | "api_error"
  | "page_error"
  | "render_error"
  | "network_error"
  | "pipeline_error"
  
  // Performance
  | "web_vital_metric";

export interface EventPayloadMap {
  user_signup: { method: "email" | "google" };
  user_login: { method: "email" | "google"; success: boolean };
  logout: Record<string, never>;
  session_start: Record<string, never>;
  session_end: { duration_seconds: number };
  
  story_view: { story_id: string; headline: string; category?: string; tags?: string[]; source_count?: number; article_count?: number };
  story_open: { story_id: string; headline: string };
  story_scroll: { story_id: string; depth_percentage: 25 | 50 | 75 | 90 | 100 };
  story_complete: { story_id: string; read_time_seconds: number };
  story_share: { story_id: string; platform: string };
  story_bookmark: { story_id: string; action: "add" | "remove" };
  story_copy_link: { story_id: string };
  story_reaction: { story_id: string; reaction_type: string };
  story_read_time: { story_id: string; duration_seconds: number };
  
  summary_view: { story_id: string; summary_type: "one_line" | "short" | "detailed" };
  summary_expand: { story_id: string };
  source_comparison_open: { story_id: string; source_count: number };
  difference_engine_open: { story_id: string; conflict_count: number };
  timeline_open: { story_id: string; timeline_length: number };
  key_facts_view: { story_id: string; fact_count: number };
  fact_check_view: { story_id: string };
  translation_used: { story_id: string; target_language: string };
  audio_summary_play: { story_id: string; action: "play" | "pause" | "complete" };
  citation_click: { story_id: string; source_name?: string; url: string };
  ai_retry: { story_id: string; ai_feature: string };
  ai_failure: { story_id: string; ai_feature: string; error_message: string };
  
  search_started: { search_term: string };
  search_completed: { search_term: string; result_count: number };
  search_result_click: { search_term: string; clicked_from: string; story_id?: string };
  search_no_results: { search_term: string };
  search_filter_applied: { filter_name: string };
  search_sort_changed: { sort_by: string };
  
  topic_follow: { topic_slug: string; topic_name: string };
  topic_unfollow: { topic_slug: string; topic_name: string };
  feed_refresh: { category_slug: string };
  recommendation_clicked: { story_id: string; recommendation_type: string };
  notification_enabled: { notification_type: string };
  notification_clicked: { notification_id: string; notification_type: string };
  
  page_view: { path: string; title: string };
  route_change: { from_path: string; to_path: string };
  menu_open: { menu_name: string };
  menu_close: { menu_name: string };
  footer_click: { link_name: string; url: string };
  header_click: { link_name: string; url: string };
  
  session_duration: { duration_seconds: number };
  engaged_session: { active_time_seconds: number };
  
  api_error: { endpoint: string; status_code?: number; error_message: string };
  page_error: { path: string; error_message: string };
  render_error: { component_name: string; error_message: string };
  network_error: { endpoint: string; error_message: string };
  pipeline_error: { pipeline_name: string; error_message: string };
  
  web_vital_metric: { metric_name: string; metric_value: number; metric_id: string; metric_rating: "good" | "needs-improvement" | "poor" };
}

export interface AnalyticsProvider {
  name: string;
  initialize(): void;
  identify(userId: string, traits?: UserTraits): void;
  setUserProperties(properties: Partial<CustomDimensions>): void;
  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void;
  pageView(path: string, title: string): void;
  reset(): void;
}
