import type { Metadata } from "next";
import { PlacementDashboard } from "./dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <PlacementDashboard />;
}
