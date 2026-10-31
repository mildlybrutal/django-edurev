import type { Metadata } from "next";
import { FacultyDashboardView } from "./faculty-views";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <FacultyDashboardView />;
}
