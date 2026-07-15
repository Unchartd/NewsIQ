---
trigger: always_on
---

# frontend.md — Frontend Coding Rules for NewsIQ

These rules govern the development, layout, and components of the client application.

## 1. Component Structure
- **Functional Components**: Write React components as functional components using standard hooks.
- **Modularity**: Extract layout segments into dedicated subcomponents under `components/` or equivalent folders. Avoid monolithic components exceeding 300 lines of code.
- **Strong Typing**: Always declare TypeScript interfaces for component props, API responses, and local states.

## 2. Interface Styling & Accessibility
- **CSS System**: Use Tailwind CSS for utility styling. Rely on design tokens defined in Tailwind config for colors, fonts, margins, and borders.
- **Animations**: Implement smooth hover/focus transitions. Ensure micro-animations use requestAnimationFrame or hardware-accelerated CSS properties.
- **Accessibility**: Use correct semantic HTML elements (e.g. `<main>`, `<article>`, `<nav>`). Ensure all interactive elements have unique and descriptive IDs.
