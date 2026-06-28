# Web Vitals & Performance Telemetry

NewsIQ tracks site loading performance and API speeds to maintain high search latency, short summaries generations, and smooth layouts.

---

## 1. Core Web Vitals (Automated)

The unified analytics script leverages Next.js's built-in `useReportWebVitals` hook in [analytics-tracker.tsx](file:///c:/Users/zakau/NewsIQ/apps/web/src/components/analytics/analytics-tracker.tsx) to capture page performance metrics:

1. **FCP (First Contentful Paint)**: Time to render the first bit of content (target: < 1.8s).
2. **LCP (Largest Contentful Paint)**: Time to render the main content block (target: < 2.5s).
3. **CLS (Cumulative Layout Shift)**: Layout stability score (target: < 0.1).
4. **INP (Interaction to Next Paint)**: Page responsiveness metric (target: < 200ms).
5. **TTFB (Time to First Byte)**: Server response speed (target: < 800ms).

Every metric is dispatched to registered analytics providers:
```typescript
analytics.track("web_vital_metric", {
  metric_name: "LCP",
  metric_value: 1450,
  metric_id: "v4-1718-29",
  metric_rating: "good"
});
```

---

## 2. API Response & Network Failures

Axios interceptors in [api-client.ts](file:///c:/Users/zakau/NewsIQ/apps/web/src/lib/api-client.ts) catch server errors and log them to monitor health and pipeline performance:

- **`api_error`**: Logged when the backend server returns a non-2xx status code (e.g. 500, 400).
- **`network_error`**: Logged when the client fails to reach the backend entirely (e.g. DNS or connection timeouts).
