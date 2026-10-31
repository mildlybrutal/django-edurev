import type { Metadata } from "next";
import { Suspense } from "react";
import { PlanView } from "./plan-view";

export const metadata: Metadata = { title: "Preparation Plan" };

export default function Page() {
  return (
    <Suspense>
      <PlanView />
    </Suspense>
  );
}
