import type { Metadata } from "next";
import { RecruiterAccessView } from "./recruiter-access-view";

export const metadata: Metadata = { title: "Recruiter Access" };

export default function Page() {
  return <RecruiterAccessView />;
}
