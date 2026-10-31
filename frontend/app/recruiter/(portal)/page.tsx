import type { Metadata } from "next";
import { RecruiterHome } from "./recruiter-views";

export const metadata: Metadata = { title: "Recruiter portal" };

export default function Page() {
  return <RecruiterHome />;
}
