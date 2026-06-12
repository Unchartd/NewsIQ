"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, TrendingUp, Bookmark, User } from "lucide-react";

export function MobileNav() {
  const pathname = usePathname();

  const navItems = [
    { label: "Home", href: "/home", icon: Home },
    { label: "Trending", href: "/trending", icon: TrendingUp },
    { label: "Bookmarks", href: "/bookmarks", icon: Bookmark },
    { label: "Profile", href: "/profile", icon: User },
  ];

  return (
    <div className="lg:hidden fixed bottom-0 left-0 right-0 z-50 h-16 border-t border-border/60 bg-background/80 backdrop-blur-xl flex items-center justify-around px-4 pb-safe">
      {navItems.map((item) => {
        const isActive = pathname === item.href;
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-colors ${
              isActive
                ? "text-primary font-semibold"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className={`w-5 h-5 ${isActive ? "stroke-[2.5px]" : "stroke-[2px]"}`} />
            <span className="text-[10px] mt-1 font-medium tracking-tight">
              {item.label}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
