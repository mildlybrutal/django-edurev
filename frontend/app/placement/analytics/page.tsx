import type { Metadata } from "next";
import { AnalyticsView } from "./analytics-view";

export const metadata: Metadata = { title: "Batch Analytics" };

export default function Page() {
  return <AnalyticsView />;
}
