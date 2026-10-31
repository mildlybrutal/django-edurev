import type { Metadata } from "next";
import { StudentDashboardView } from "./dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <StudentDashboardView />;
}
