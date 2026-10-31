import type { Metadata } from "next";
import { StudentDetail } from "@/components/domain/student-detail";

export const metadata: Metadata = { title: "Student" };

export default async function Page({ params }: PageProps<"/faculty/students/[id]">) {
  const { id } = await params;
  return <StudentDetail id={Number(id)} />;
}
