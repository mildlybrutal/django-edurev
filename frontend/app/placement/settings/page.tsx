import type { Metadata } from "next";
import { SettingsView } from "./settings-view";

export const metadata: Metadata = { title: "Scoring & Rubrics" };

export default function Page() {
  return <SettingsView />;
}
