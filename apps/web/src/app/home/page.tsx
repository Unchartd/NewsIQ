import type { Metadata } from "next";
import { HomeContent } from "./home-content";

export const metadata: Metadata = {
  title: "Home Feed",
};

export default function HomePage() {
  return <HomeContent />;
}
