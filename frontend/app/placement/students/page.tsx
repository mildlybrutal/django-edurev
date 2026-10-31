import type { Metadata } from "next";
import { StudentsList } from "./students-views";

export const metadata: Metadata = { title: "Students" };

export default function Page() {
  return <StudentsList />;
}
