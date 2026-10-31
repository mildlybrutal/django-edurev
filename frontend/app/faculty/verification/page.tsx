import type { Metadata } from "next";
import { VerificationQueue } from "../faculty-views";

export const metadata: Metadata = { title: "Verification Queue" };

export default function Page() {
  return <VerificationQueue />;
}
