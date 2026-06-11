# AI News Intelligence Platform — Complete UX Flow Document

This document defines every screen, navigation path, user action, button behavior, success states, error states, and empty states so that an AI coding agent can implement the product without making assumptions.

---

# Global Navigation

## Desktop

Top Navbar

```
Logo
Search
Trending
Categories
Locations
Bookmarks
Profile
Theme Toggle
```

---

## Mobile

Bottom Navigation

```
Home
Trending
Search
Bookmarks
Profile
```

---

# Application Routes

```text
/
├── onboarding
├── login
├── signup
├── home
├── trending
├── category/[slug]
├── location/[country]/[state]/[city]
├── story/[storyId]
├── search
├── bookmarks
├── profile
├── preferences
├── notifications
├── digest
├── settings
├── premium
├── admin
├── 404
└── error
```

---

# 1. Landing Page

Route

```text
/
```

---

## Components

Hero section

Value proposition

Trending stories preview

Category cards

CTA buttons

Footer

---

## Buttons

### Start Reading

Action

```text
→ /home
```

---

### Sign In

Action

```text
→ /login
```

---

### Get Premium

Action

```text
→ /premium
```

---

## Success State

Page loads.

---

## Error State

Unable to load trending stories.

Show:

```
Could not load stories.
Retry
```

---

## Empty State

No trending stories available.

Show:

```
No stories available right now.
```

---

# 2. Authentication

---

# Login

Route

```text
/login
```

---

Fields

Email

Password

Remember me

---

Buttons

### Continue with Google

Success

```text
→ /home
```

Failure

Toast:

```
Authentication failed.
```

---

### Login

Success

```text
→ previous page
```

Failure

```
Invalid credentials
```

---

### Forgot Password

```text
→ /forgot-password
```

---

# Signup

Route

```text
/signup
```

Fields

Name

Email

Password

Confirm Password

---

Success

```text
→ onboarding
```

---

Errors

Email exists

Weak password

Network failure

---

# 3. Onboarding

Route

```text
/onboarding
```

---

Step 1

Choose categories

Checkboxes

```
Politics
Technology
Business
Sports
Health
Science
Entertainment
Weather
```

---

Button

Continue

Validation

At least one category required.

---

Step 2

Choose countries

Multi-select

Examples

```
India
USA
UK
Japan
```

---

Step 3

Cities

```
Bengaluru
Delhi
Mumbai
London
```

---

Step 4

Summary preference

Radio

```
1-line
Short
Detailed
```

---

Finish

Success

```text
→ /home
```

---

# 4. Home Feed

Route

```text
/home
```

---

Components

Search bar

Category tabs

Location selector

Trending banner

Story cards

Infinite scroll

---

Story Card

Contains

Headline

Summary

Location

Category

Trending score

Sources count

Time

Bookmark icon

---

Buttons

### Open Story

```text
→ /story/[id]
```

---

### Bookmark

Success

Heart filled

Toast

```
Story saved
```

Failure

```
Unable to save story
```

---

### Share

Native share menu

Copy URL

---

### Expand Summary

Switch

```
1-line
Short
Detailed
```

---

Empty State

```
No stories found.
```

Button

Refresh

---

Error State

```
Unable to fetch stories.
Retry
```

---

# 5. Search Page

Route

```text
/search
```

---

Components

Search input

Filters

Recent searches

Results

---

Filters

Category

Country

City

Time range

Trending only

---

Buttons

Search

Clear filters

---

Success

Show stories.

---

No Results

Illustration

Message

```
No matching stories found.
```

Button

Clear Filters

---

Network Error

```
Search failed.
Try again.
```

---

# 6. Trending Page

Route

```text
/trending
```

---

Tabs

Today

24 Hours

7 Days

30 Days

---

Sorting

Most discussed

Most sources

Fastest growing

---

Story Cards

Same as home.

---

Success

Show list.

---

Empty State

```
No trending stories.
```

---

# 7. Category Page

Route

```text
/category/[slug]
```

Examples

```text
/category/technology
/category/sports
```

---

Components

Header

Subcategories

Story feed

---

Actions

Open story

Bookmark

Share

---

# 8. Location Page

Route

```text
/location/india/karnataka/bengaluru
```

---

Components

Breadcrumb

```
World > India > Karnataka > Bengaluru
```

Local stories

Filters

---

Empty State

```
No stories from this region.
```

---

# 9. Story Details Page

Most important screen.

Route

```text
/story/[storyId]
```

---

Sections

---

Headline

---

Summary Switch

Buttons

```
1-line
Short
Detailed
```

Behavior

Changes displayed summary.

---

Key Facts

Location

Time

Category

People

Organizations

---

Timeline

Chronological events.

---

Source Coverage Table

Columns

Source

Focus

Published Time

Open Source

---

Buttons

### Open Original Article

Opens new tab.

---

Differences Section

Shows

Unique facts

Missing facts

Contradictions

---

Related Stories

Carousel.

---

Bookmark Button

---

Share Button

---

Success State

Story loaded.

---

Loading State

Skeleton UI.

---

Error State

```
Story unavailable.
```

Buttons

Retry

Go Home

---

# 10. Comparison Page

Route

```text
/story/[id]/comparison
```

---

Table

| Fact | Source A | Source B |
| ---- | -------- | -------- |

---

Filters

Source selection

---

Success

Show comparison.

---

Empty State

```
No differences detected.
```

---

# 11. Timeline Page

Route

```text
/story/[id]/timeline
```

---

Vertical timeline

---

Sort

Ascending

Descending

---

Success

Timeline visible.

---

Empty State

```
Timeline unavailable.
```

---

# 12. Source Page

Route

```text
/source/[source]
```

Examples

```text
/source/ndtv
/source/reuters
```

---

Components

Source details

Publisher logo

Stories

Statistics

---

Actions

Follow source

Open website

---

# 13. Bookmark Page

Route

```text
/bookmarks
```

---

Components

Saved stories

Search inside bookmarks

---

Buttons

Remove

Open

Share

---

Empty State

Illustration

```
No bookmarked stories yet.
```

---

# 14. Profile Page

Route

```text
/profile
```

---

Sections

Avatar

Name

Email

Subscription

Preferences

---

Buttons

Edit Profile

Preferences

Settings

Logout

---

Logout Success

Redirect

```text
/
```

---

# 15. Preferences Page

Route

```text
/preferences
```

---

Categories

Countries

Cities

Summary type

Theme

Language

---

Buttons

Save

Reset

---

Success

Toast

```
Preferences updated.
```

---

Failure

```
Unable to save changes.
```

---

# 16. Daily Digest Page

Route

```text
/digest
```

---

Cards

Morning digest

Evening digest

Weekly digest

---

Buttons

Read

Download

---

Empty State

```
No digest available.
```

---

# 17. Notification Page

Route

```text
/notifications
```

---

Cards

Breaking news

Trending stories

Digest ready

---

Buttons

Mark read

Delete

---

Empty State

```
You're all caught up.
```

---

# 18. Premium Page

Route

```text
/premium
```

---

Plans

Free

Pro

Enterprise

---

Buttons

Upgrade

Contact Sales

---

Success

Badge

```
Premium activated.
```

---

Payment Error

```
Payment failed.
```

Retry

---

# 19. Settings

Route

```text
/settings
```

---

Sections

Theme

Notifications

Privacy

Security

Account

---

Danger Zone

Delete account

---

Delete Flow

Modal

```
Are you sure?
```

Buttons

Cancel

Delete

---

Success

```text
→ /
```

---

# 20. AI Chat (Phase 2)

Route

```text
/chat
```

---

Input

Ask a question

---

Examples

```
Why is this happening?

Explain like I'm 10.

What changed since yesterday?
```

---

Response Types

Bullets

Paragraph

Timeline

Facts only

---

Error

```
AI temporarily unavailable.
```

---

# 21. Admin Dashboard

Route

```text
/admin
```

Role

Admin only

---

Sections

Articles

Stories

Sources

Users

Analytics

Errors

Jobs

---

Actions

Reprocess story

Delete article

Recompute embeddings

Ban user

---

# Global Components

---

## Search Bar

Visible everywhere.

Behavior

Typing:

Debounce 300ms

Fetch suggestions

---

Enter key

```text
→ /search?q=value
```

---

No suggestions

```
No matches found.
```

---

## Theme Toggle

Light

Dark

System

---

Persisted in localStorage.

---

## Toast Notifications

Success

Green

Examples

```
Story saved.

Preferences updated.

Login successful.
```

---

Warning

Yellow

```
Network slow.
```

---

Error

Red

```
Something went wrong.
```

---

# Infinite Scroll Behavior

Trigger

70% viewport reached

---

Loading

Skeleton cards

---

Failure

Button

```
Load More
```

---

End

```
You've reached the end.
```

---

# HTTP Errors

### 401

```
Please sign in.
```

Button

Login

---

### 403

```
Access denied.
```

---

### 404

```
Page not found.
```

Button

Go Home

---

### 429

```
Too many requests.
Please try later.
```

---

### 500

```
Internal server error.
```

Retry button

---

# Complete User Journey

```text
Landing
    ↓
Signup/Login
    ↓
Onboarding
    ↓
Home Feed
    ↓
Open Story
    ↓
Read Summary
    ↓
Compare Sources
    ↓
Bookmark Story
    ↓
Receive Daily Digest
    ↓
Upgrade to Premium
    ↓
Use AI Chat
```

---

## Recommended Information Architecture

```text
App
│
├── Public
│     ├── Landing
│     ├── Login
│     └── Signup
│
├── News
│     ├── Home
│     ├── Trending
│     ├── Search
│     ├── Categories
│     ├── Locations
│     └── Story Details
│
├── Personal
│     ├── Bookmarks
│     ├── Digest
│     ├── Notifications
│     ├── Preferences
│     └── Profile
│
├── Premium
│
├── AI Chat (Phase 2)
│
└── Admin
```

This level of detail is sufficient for an AI coding agent to generate the complete Next.js frontend and associated API interactions with minimal ambiguity.
