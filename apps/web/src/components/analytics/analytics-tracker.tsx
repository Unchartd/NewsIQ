"use client";

import { useEffect, useRef, Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { analytics } from "@/lib/analytics/service";

// Throttling helper
function throttle(func: (...args: any[]) => void, wait: number) {
  let timeout: any = null;
  let previous = 0;
  
  return function(this: any, ...args: any[]) {
    const now = Date.now();
    if (!previous) previous = now;
    const remaining = wait - (now - previous);
    
    if (remaining <= 0 || remaining > wait) {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      previous = now;
      func.apply(this, args);
    } else if (!timeout) {
      timeout = setTimeout(() => {
        previous = Date.now();
        timeout = null;
        func.apply(this, args);
      }, remaining);
    }
  };
}

export function AnalyticsTracker() {
  const pathname = usePathname();

  // Keep track of loaded path to manage page views and reading sessions
  const currentPathRef = useRef<string>("");
  const activeTimeRef = useRef<number>(0);
  const lastInteractionRef = useRef<number>(Date.now());
  const isIdleRef = useRef<boolean>(false);
  const scrollThresholdsRef = useRef<Set<number>>(new Set());

  // Flush active time helper
  const flushActiveTime = (path: string) => {
    const seconds = Math.round(activeTimeRef.current / 1000);
    if (seconds <= 0) return;
    
    const storyIdMatch = path.match(/\/story\/([a-zA-Z0-9-]+)/);
    if (storyIdMatch) {
      const storyId = storyIdMatch[1];
      analytics.track("story_read_time", {
        story_id: storyId,
        duration_seconds: seconds,
      });

      // If user read for a substantial time and scrolled far, log story_complete
      const maxScroll = Math.max(...Array.from(scrollThresholdsRef.current), 0);
      if (maxScroll >= 90) {
        analytics.track("story_complete", {
          story_id: storyId,
          read_time_seconds: seconds,
        });
      }
    } else {
      analytics.track("engaged_session", {
        active_time_seconds: seconds,
      });
    }
    
    activeTimeRef.current = 0;
  };

  const handlePageChange = (fullPath: string) => {
    if (fullPath === currentPathRef.current) return;
    
    // Page is changing! Flush the previous page's active time before updating
    if (currentPathRef.current) {
      flushActiveTime(currentPathRef.current);
    }
    
    currentPathRef.current = fullPath;
    activeTimeRef.current = 0;
    scrollThresholdsRef.current.clear();
    lastInteractionRef.current = Date.now();
    isIdleRef.current = false;
  };

  // Active Time & Scroll Depth Tracker
  useEffect(() => {
    const handleInteraction = () => {
      lastInteractionRef.current = Date.now();
      if (isIdleRef.current) {
        isIdleRef.current = false;
      }
    };

    window.addEventListener("mousemove", handleInteraction);
    window.addEventListener("keydown", handleInteraction);
    window.addEventListener("scroll", handleInteraction);
    window.addEventListener("click", handleInteraction);
    window.addEventListener("touchstart", handleInteraction);

    // Active time accumulator loop
    const timeInterval = setInterval(() => {
      if (document.hidden) return; // tab is hidden
      
      const now = Date.now();
      const timeSinceLastInteraction = now - lastInteractionRef.current;
      
      // If no interaction for 10 seconds, classify user as idle
      if (timeSinceLastInteraction > 10000) {
        isIdleRef.current = true;
      }

      if (!isIdleRef.current) {
        activeTimeRef.current += 1000;
      }
    }, 1000);

    // Scroll depth tracking
    const checkScrollDepth = throttle(() => {
      if (typeof window === "undefined" || !pathname) return;
      
      const scrollHeight = document.documentElement.scrollHeight;
      const clientHeight = document.documentElement.clientHeight;
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      
      if (scrollHeight <= clientHeight) return;
      
      const scrollPercent = Math.round(((scrollTop + clientHeight) / scrollHeight) * 100);
      const thresholds = [25, 50, 75, 90, 100];
      
      thresholds.forEach((threshold) => {
        if (scrollPercent >= threshold && !scrollThresholdsRef.current.has(threshold)) {
          scrollThresholdsRef.current.add(threshold);
          
          const storyIdMatch = pathname.match(/\/story\/([a-zA-Z0-9-]+)/);
          if (storyIdMatch) {
            analytics.track("story_scroll", {
              story_id: storyIdMatch[1],
              depth_percentage: threshold as any,
            });
          }
        }
      });
    }, 250);

    window.addEventListener("scroll", checkScrollDepth);

    // Tab visibility changes
    const handleVisibilityChange = () => {
      if (document.hidden) {
        flushActiveTime(currentPathRef.current);
      } else {
        lastInteractionRef.current = Date.now();
        isIdleRef.current = false;
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    // Flush active time before window exit/unload
    const handleBeforeUnload = () => {
      flushActiveTime(currentPathRef.current);
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      clearInterval(timeInterval);
      window.removeEventListener("mousemove", handleInteraction);
      window.removeEventListener("keydown", handleInteraction);
      window.removeEventListener("scroll", handleInteraction);
      window.removeEventListener("click", handleInteraction);
      window.removeEventListener("touchstart", handleInteraction);
      window.removeEventListener("scroll", checkScrollDepth);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [pathname]);

  // Next.js Core Web Vitals Tracking
  useReportWebVitals((metric) => {
    const rating = metric.rating === "good" || metric.rating === "needs-improvement" || metric.rating === "poor"
      ? metric.rating
      : "good";
    
    analytics.track("web_vital_metric", {
      metric_name: metric.name,
      metric_value: metric.value,
      metric_id: metric.id,
      metric_rating: rating,
    });
  });

  return (
    <Suspense fallback={null}>
      <AnalyticsPageViewTracker onPageChange={handlePageChange} />
    </Suspense>
  );
}

interface PageViewProps {
  onPageChange: (fullPath: string) => void;
}

function AnalyticsPageViewTracker({ onPageChange }: PageViewProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (!pathname) return;
    const fullPath = pathname + (searchParams?.toString() ? `?${searchParams.toString()}` : "");
    onPageChange(fullPath);
    analytics.pageView(fullPath, document.title);
  }, [pathname, searchParams, onPageChange]);

  return null;
}
