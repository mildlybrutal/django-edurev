import type { Metadata } from "next";
import { MenteesView } from "../faculty-views";

export const metadata: Metadata = { title: "My Students" };

export default function Page() {
  return <MenteesView />;
}
