import type { Metadata } from "next";
import { SkillsManager } from "./skills-manager";

export const metadata: Metadata = { title: "Manage Skills" };

export default function Page() {
  return <SkillsManager />;
}
