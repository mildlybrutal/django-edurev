import type { Metadata } from "next";
import { DriveDetail } from "./drive-detail";

export const metadata: Metadata = { title: "Drive" };

export default async function Page({ params }: PageProps<"/student/drives/[id]">) {
  const { id } = await params;
  return <DriveDetail id={Number(id)} />;
}
