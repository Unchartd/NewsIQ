"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  TrendingUp,
  Bookmark,
  Landmark,
  Cpu,
  Briefcase,
  Trophy,
  HeartPulse,
  FlaskConical,
  Clapperboard,
  CloudSun,
  Globe,
  ChevronLeft,
  ChevronRight,
  Settings,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useUIStore } from "@/stores/ui-store";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const mainNav: NavItem[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Trending", href: "/trending", icon: TrendingUp },
  { label: "Bookmarks", href: "/bookmarks", icon: Bookmark },
];

const categoryIcons: Record<string, LucideIcon> = {
  politics: Landmark,
  technology: Cpu,
  business: Briefcase,
  sports: Trophy,
  health: HeartPulse,
  science: FlaskConical,
  entertainment: Clapperboard,
  weather: CloudSun,
  world: Globe,
};

const categories: NavItem[] = [
  { label: "Politics", href: "/category/politics", icon: Landmark },
  { label: "Technology", href: "/category/technology", icon: Cpu },
  { label: "Business", href: "/category/business", icon: Briefcase },
  { label: "Sports", href: "/category/sports", icon: Trophy },
  { label: "Health", href: "/category/health", icon: HeartPulse },
  { label: "Science", href: "/category/science", icon: FlaskConical },
  { label: "Entertainment", href: "/category/entertainment", icon: Clapperboard },
  { label: "Weather", href: "/category/weather", icon: CloudSun },
  { label: "World", href: "/category/world", icon: Globe },
];

function NavLink({
  item,
  collapsed,
  isActive,
}: {
  item: NavItem;
  collapsed: boolean;
  isActive: boolean;
}) {
  const content = (
    <Link
      href={item.href}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
        isActive
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      } ${collapsed ? "justify-center" : ""}`}
    >
      <item.icon
        className={`w-[18px] h-[18px] flex-shrink-0 transition-transform group-hover:scale-110 ${
          isActive ? "text-primary" : ""
        }`}
      />
      {!collapsed && (
        <span className="truncate">{item.label}</span>
      )}
      {isActive && !collapsed && (
        <motion.div
          layoutId="active-indicator"
          className="ml-auto w-1.5 h-1.5 rounded-full bg-primary"
        />
      )}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger render={content} />
        <TooltipContent side="right" sideOffset={8}>
          {item.label}
        </TooltipContent>
      </Tooltip>
    );
  }

  return content;
}

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useUIStore();
  const collapsed = !sidebarOpen;

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside
        className={`fixed lg:sticky top-16 left-0 z-40 h-[calc(100vh-4rem)] border-r border-border/60 bg-background transition-all duration-300 flex flex-col ${
          collapsed ? "w-[60px]" : "w-[240px]"
        } ${
          // Mobile: slide in/out
          sidebarOpen
            ? "translate-x-0"
            : "-translate-x-full lg:translate-x-0"
        }`}
      >
        <ScrollArea className="flex-1 py-3 px-2">
          {/* Main Nav */}
          <div className="space-y-1">
            {mainNav.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                collapsed={collapsed}
                isActive={pathname === item.href}
              />
            ))}
          </div>

          {!collapsed && (
            <div className="px-3 mt-5 mb-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                Categories
              </p>
            </div>
          )}

          {collapsed && <Separator className="my-3" />}

          {/* Categories */}
          <div className="space-y-1">
            {categories.map((item) => (
              <NavLink
                key={item.href}
                item={item}
                collapsed={collapsed}
                isActive={pathname === item.href}
              />
            ))}
          </div>
        </ScrollArea>

        {/* Collapse toggle — desktop only */}
        <div className="hidden lg:flex items-center justify-center border-t border-border/60 py-2">
          <Button
            variant="ghost"
            size="icon"
            className="w-8 h-8 rounded-lg"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </Button>
        </div>
      </aside>
    </>
  );
}
