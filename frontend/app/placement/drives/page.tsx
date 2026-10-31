import type { Metadata } from "next";
import { DrivesList } from "./drives-list";

export const metadata: Metadata = { title: "Placement Drives" };

export default function Page() {
  return <DrivesList />;
}
