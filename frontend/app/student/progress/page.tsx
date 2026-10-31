import type { Metadata } from "next";
import { ProgressView } from "./progress-view";

export const metadata: Metadata = { title: "Progress" };

export default function Page() {
  return <ProgressView />;
}
