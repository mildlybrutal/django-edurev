import type { Metadata } from "next";
import { EvidenceView } from "./evidence-view";

export const metadata: Metadata = { title: "Skills & Evidence" };

export default function Page() {
  return <EvidenceView />;
}
