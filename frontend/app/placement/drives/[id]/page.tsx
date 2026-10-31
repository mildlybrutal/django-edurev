import type { Metadata } from "next";
import { DriveManage } from "./drive-manage";

export const metadata: Metadata = { title: "Drive" };

export default async function Page({ params }: PageProps<"/placement/drives/[id]">) {
  const { id } = await params;
  return <DriveManage id={Number(id)} />;
}
