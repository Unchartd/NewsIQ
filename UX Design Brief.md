# UI/UX Design Brief

# AI News Intelligence Platform

---

# 1. Design Vision

The product should feel like a combination of:

* **Apple News** (clean reading experience)
* **Perplexity AI** (AI-first layout)
* **Linear** (minimalism)
* **Bloomberg Terminal (modernized)** (information density)
* **Notion** (clarity and whitespace)
* **Ground News** (source comparison)

### Keywords

* Clean
* Trustworthy
* Intelligent
* Minimal
* Data-rich
* Fast
* Neutral
* Professional

The design should prioritize **understanding over entertainment**.

---

# 2. Design Language

### Style

Modern AI-native interface.

Avoid:

* Heavy gradients
* Glassmorphism
* Excessive shadows
* Clickbait colors
* Visual clutter

Prefer:

* Rounded corners
* Soft shadows
* Clear hierarchy
* Plenty of whitespace
* High readability

---

# 3. Theme Support

Must support:

### Light Theme (default)

Professional newsroom feel.

### Dark Theme

For power users and night reading.

### System Theme

Automatically follows OS settings.

---

# 4. Color Palette

---

## Light Theme

### Background

```css
#FFFFFF
```

---

### Secondary Background

```css
#F8FAFC
```

---

### Card Background

```css
#FFFFFF
```

---

### Border

```css
#E2E8F0
```

---

### Primary Text

```css
#0F172A
```

---

### Secondary Text

```css
#64748B
```

---

### Accent Color

Blue

```css
#2563EB
```

Purpose:

* Active tabs
* Buttons
* Links

---

### Success

Green

```css
#10B981
```

---

### Warning

Orange

```css
#F59E0B
```

---

### Error

Red

```css
#EF4444
```

---

### Trending Indicator

Purple

```css
#9333EA
```

---

## Dark Theme

Background

```css
#020617
```

Card

```css
#0F172A
```

Border

```css
#1E293B
```

Primary Text

```css
#F8FAFC
```

Secondary Text

```css
#94A3B8
```

Accent

```css
#3B82F6
```

---

# 5. Typography

### Font Family

#### Primary

Inter

Fallback:

```css
Inter, system-ui, sans-serif
```

---

### Monospace

JetBrains Mono

Used for:

* Timeline
* Technical stats
* IDs

---

# Font Scale

### H1

48px

Weight:

700

---

### H2

36px

Weight:

700

---

### H3

24px

Weight:

600

---

### H4

20px

Weight:

600

---

### Body Large

18px

Weight:

400

---

### Body

16px

Weight:

400

---

### Caption

14px

Weight:

400

---

### Small Labels

12px

Weight:

500

---

Line Height

1.6

---

# 6. Grid System

12-column layout.

Max width:

```css
1440px
```

Content width:

```css
1280px
```

Spacing scale:

```css
4
8
12
16
24
32
48
64
```

---

# 7. Border Radius

Cards

```css
20px
```

Buttons

```css
14px
```

Inputs

```css
12px
```

Tags

```css
999px
```

---

# 8. Shadow System

Subtle only.

Cards:

```css
0 1px 3px rgba(0,0,0,.08)
```

Hover:

```css
0 8px 24px rgba(0,0,0,.08)
```

---

# 9. Layout Direction

---

## Desktop

```text
--------------------------------
Navbar
--------------------------------

Sidebar | Content | Right Panel

--------------------------------
```

---

## Mobile

```text
Navbar

Content

Bottom Navigation
```

---

# 10. Navigation Structure

---

## Top Navbar

Height

80px

Contains:

```text
Logo

Search

Trending

Categories

Bookmarks

Notifications

Profile

Theme Toggle
```

---

# Sidebar

Width

280px

Contains

```text
Home
Trending
Politics
Technology
Business
Sports
Health
Science
Bookmarks
Digest
Settings
```

---

# Right Sidebar

Width

320px

Contains

```text
Trending Topics

Popular Sources

Latest Updates

Weather Widget
```

---

# 11. Dashboard Structure

```text
----------------------------------------------------
Navbar
----------------------------------------------------

Sidebar

Home Feed

Right Panel

----------------------------------------------------
```

---

## Home Feed Sections

### Hero Section

Trending Story

Large card

---

### Category Tabs

Scrollable.

---

### Stories Feed

Infinite scroll.

---

### Personalized Stories

Optional.

---

# 12. Story Card Design

Card Radius

20px

Padding

24px

---

Contains

Headline

Summary

Metadata

Tags

Actions

---

Structure

```text
Headline

Short Summary

Location • Time • Category

Source Count

Bookmark Share
```

---

Hover

Scale

```css
1.01
```

Transition

200ms

---

# 13. Story Detail Page

Three-column layout.

---

### Center Column

Headline

Summary switch

Timeline

Differences

Sources

---

### Left Sidebar

Category

Tags

Bookmark

Share

---

### Right Sidebar

Related stories

Trending stories

---

Structure

```text
Headline

1-line / Short / Detailed

Key Facts

Timeline

Source Coverage

Differences

References

Related Stories
```

---

# 14. Search Experience

Inspired by:

Perplexity AI.

---

Sticky search bar.

Autocomplete.

Recent searches.

Filters drawer.

---

Results appear instantly.

---

# 15. Component System

---

# Buttons

Primary

Blue background

White text

Height

48px

---

Secondary

Gray border

Transparent

---

Ghost

No border

---

Danger

Red

---

Loading State

Spinner

Disabled.

---

# Inputs

Height

48px

Rounded

12px

---

Focus

Blue ring

---

# Cards

Padding

24px

Radius

20px

---

# Badges

Category chips.

Examples

```text
Technology

Weather

Politics
```

Rounded pills.

---

# Tables

Source comparison.

Rows

56px

Sticky header.

Hover highlight.

---

# Tabs

Underline style.

Animated.

---

# Dropdowns

Floating menu.

Shadow depth 2.

---

# Toasts

Bottom right.

Duration

3 seconds.

---

# Skeleton Loading

Always use.

Cards

Timeline

Tables

---

# Empty States

Illustrations.

Message.

Action button.

---

# 16. Timeline Component

Inspired by:

GitHub activity.

---

Vertical line.

Events connected.

---

Structure

```text
10:00

Heavy rain starts

↓

11:30

Roads flooded

↓

12:00

Authorities issue warning
```

---

# 17. Source Comparison Table

Inspired by:

Ground News.

---

Columns

Fact

Source A

Source B

Source C

---

Missing values

Gray dash.

---

Contradictions

Red highlight.

---

Unique facts

Blue highlight.

---

# 18. Trending Section

Cards with:

Fire icon

Trend score

Category

Source count

---

Color

Purple accent.

---

# 19. Mobile Design

Mobile-first.

---

Breakpoints

```css
640
768
1024
1280
1536
```

---

Cards become single column.

---

Sidebar becomes drawer.

---

Bottom navigation:

```text
Home

Trending

Search

Bookmarks

Profile
```

---

Floating search button.

---

# 20. Animations

Library

Framer Motion.

---

Duration

150–250ms.

---

Use for:

Hover

Expand

Tabs

Modals

Page transitions

---

Avoid:

Long animations.

---

# 21. Accessibility

WCAG AA.

---

Contrast

4.5:1

---

Keyboard navigation.

---

Screen reader support.

---

Visible focus states.

---

ARIA labels.

---

# 22. User Experience Principles

---

## 1. Reading First

Content before decoration.

---

## 2. Reduce Cognitive Load

No clutter.

No excessive colors.

---

## 3. Progressive Disclosure

Show:

1-line summary

Expand only if needed.

---

## 4. Transparency

Always show:

Publisher

Timestamp

Original source

---

## 5. Fast Scanning

Users should understand a story in under 30 seconds.

---

## 6. Familiar Interactions

No unusual navigation.

---

## 7. Mobile First

Most users consume news on mobile.

---

# 23. Design Inspirations

### Perplexity AI

Search experience.

---

### Apple News

Reading layout.

---

### Linear

Spacing and minimalism.

---

### Notion

Typography.

---

### Ground News

Comparison tables.

---

### Bloomberg

Information density.

---

### Google News

Card structure.

---

# 24. Suggested shadcn Components

```text
Button
Card
Tabs
Table
Dialog
Popover
DropdownMenu
Tooltip
Badge
Accordion
Avatar
Skeleton
Sheet
Drawer
Breadcrumb
Pagination
ScrollArea
Toast
```

---

# 25. AI Builder Instructions

### Stack

* Next.js 15
* TypeScript
* Tailwind v4
* shadcn/ui
* Framer Motion
* Lucide Icons

---

### Overall Style

> Build a premium AI-native news intelligence platform with the cleanliness of Apple News, the information density of Bloomberg, the interaction quality of Linear, and the AI-first experience of Perplexity. Use rounded cards, subtle shadows, Inter typography, blue accent colors, responsive layouts, skeleton loading, and dark mode support. Prioritize readability and trust over flashy visuals.

---

## Desired Feel

**"A modern Bloomberg + Perplexity + Apple News experience designed for the AI era."**
