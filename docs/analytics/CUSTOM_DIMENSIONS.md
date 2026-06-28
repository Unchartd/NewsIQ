# NewsIQ Custom Dimensions & Metrics

This document lists all Custom Dimensions and Custom Metrics configured in the NewsIQ analytics architecture and mapping directly to Google Analytics 4 (GA4).

## 1. Custom Dimensions (Event Scope)

| Parameter Name | GA4 Dimension Name | Scope | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `story_id` | Story ID | Event | String | Database UUID of the news story cluster. |
| `headline` | Story Headline | Event | String | The primary clustered headline. |
| `story_category` | Story Category | Event | String | Slug of the primary category (e.g. `politics`). |
| `news_source` | News Source | Event | String | Name of the publisher publishing a specific article (e.g. `Reuters`). |
| `summary_type` | Summary Type | Event | String | Selected depth depth: `one_line`, `short`, or `detailed`. |
| `ai_feature` | AI Feature | Event | String | The name of the AI feature active (e.g. `difference_engine`). |
| `theme` | Theme | Event | String | Active layout theme: `light`, `dark`, or `system`. |
| `referral_source` | Referral Source | Event | String | Referral URL parsed from the initial session launch. |
| `experiment_id` | Experiment ID | Event | String | Bucket key for active A/B testing variations. |

## 2. Custom Dimensions (User Scope)

| Parameter Name | GA4 User Property Name | Scope | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `user_tier` | User Tier | User | String | Account tier class: `guest`, `user`, `premium`, or `admin`. |
| `subscription_status` | Subscription Status | User | String | Payment status plan: `free`, `pro`, or `enterprise`. |

## 3. Custom Metrics (Event Scope)

| Parameter Name | GA4 Metric Name | Scope | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `duration_seconds` | Active Reading Duration | Event | Integer | Amount of seconds user was actively interacting on the page. |
| `conflict_count` | Clustered Conflicts Count | Event | Integer | Number of source contradictions identified in the Difference Engine. |
| `timeline_length` | Timeline Event Count | Event | Integer | Number of timeline events generated for the story. |
| `metric_value` | Web Vital Metric Value | Event | Integer | Score or milliseconds duration reported by Web Vitals. |
