import type { Metadata } from "next";
import { DrivesView } from "./drives-view";

export const metadata: Metadata = { title: "Placement Drives" };

export default function Page() {
  return <DrivesView />;
}
