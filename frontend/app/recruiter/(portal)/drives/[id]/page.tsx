import type { Metadata } from "next";
import { CandidateSearch } from "../../recruiter-views";

export const metadata: Metadata = { title: "Candidates" };

export default async function Page({ params }: PageProps<"/recruiter/drives/[id]">) {
  const { id } = await params;
  return <CandidateSearch driveId={Number(id)} />;
}
