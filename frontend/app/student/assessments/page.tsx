import type { Metadata } from "next";
import { AssessmentHistory } from "./assessments-view";

export const metadata: Metadata = { title: "Assessments" };

export default function Page() {
  return <AssessmentHistory />;
}
