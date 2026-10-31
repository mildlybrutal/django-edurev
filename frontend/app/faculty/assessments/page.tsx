import type { Metadata } from "next";
import { RecordAssessments } from "../faculty-views";

export const metadata: Metadata = { title: "Assessments & Mock Interviews" };

export default function Page() {
  return <RecordAssessments />;
}
