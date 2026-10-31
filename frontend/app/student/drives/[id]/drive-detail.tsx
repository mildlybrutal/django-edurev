"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { EvaluationView } from "@/components/domain/evaluation";
import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { DriveStatusBadge, RegistrationBadge } from "@/components/ui/status";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { get, post } from "@/lib/api/request";
import type { Evaluation } from "@/lib/api/types";

export function DriveDetail({ id }: { id: number }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const drive = useQuery({
    queryKey: ["drive", id],
    queryFn: async () => unwrap(await api.GET("/api/v1/drives/{id}/", { params: { path: { id } } })),
  });
  const evaluation = useQuery({
    queryKey: ["drive", id, "evaluation"],
    queryFn: () => get<Evaluation>(`/api/v1/drives/${id}/my-evaluation/`),
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["drive", id] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const register = useMutation({
    meta: { toast: "Registered for this drive" },
    mutationFn: () => post(`/api/v1/drives/${id}/register/`),
    onSuccess: refresh,
  });
  const withdraw = useMutation({
    meta: { toast: "Registration withdrawn" },
    mutationFn: () => post(`/api/v1/drives/${id}/withdraw/`),
    onSuccess: refresh,
  });
  const plan = useMutation({
    meta: { toast: "Preparation plan created" },
    mutationFn: () => post<{ id: number }>("/api/v1/preparation-plans/", { drive_id: id }),
    onSuccess: (p) => router.push(`/student/plan?plan=${p.id}`),
  });

  return (
    <QueryState query={drive}>
      {(d) => (
        <>
          <PageHeader
            title={`${d.company.name} — ${d.role_title}`}
            description={[d.location, d.compensation, d.drive_date && `Drive on ${d.drive_date}`]
              .filter(Boolean)
              .join(" · ")}
            actions={<DriveStatusBadge status={d.status ?? ""} label={d.status_label} />}
          />
          <QueryState query={evaluation}>
            {(ev) => (
              <div className="flex flex-col gap-5">
                <Card>
                  <CardHeader title="Your next steps" />
                  <CardBody className="flex flex-wrap items-center gap-3">
                    <span className="text-sm">
                      Registration: <RegistrationBadge status={ev.registration?.status} />
                    </span>
                    {ev.registration_open && (!ev.registration || ev.registration.status === "withdrawn") && (
                      <Button
                        onClick={() => register.mutate()}
                        disabled={register.isPending || !ev.eligibility.is_eligible}
                        title={ev.eligibility.is_eligible ? undefined : "You do not meet the eligibility criteria"}
                      >
                        Register
                      </Button>
                    )}
                    {ev.registration_open && ev.registration?.status === "registered" && (
                      <Button variant="secondary" onClick={() => withdraw.mutate()} disabled={withdraw.isPending}>
                        Withdraw
                      </Button>
                    )}
                    {ev.gaps.length > 0 &&
                      (ev.plan_id ? (
                        <Link href={`/student/plan?plan=${ev.plan_id}`} className="text-sm text-primary">
                          Open your preparation plan
                        </Link>
                      ) : (
                        <Button variant="secondary" onClick={() => plan.mutate()} disabled={plan.isPending}>
                          Create a preparation plan from these gaps
                        </Button>
                      ))}
                    {[register.error, withdraw.error, plan.error].map((e, i) =>
                      e ? <FormError key={i} message={errorMessage(e)} /> : null,
                    )}
                  </CardBody>
                </Card>
                <EvaluationView evaluation={ev} forStudent />
                <JobDescription drive={d} />
              </div>
            )}
          </QueryState>
        </>
      )}
    </QueryState>
  );
}

function JobDescription({ drive }: { drive: Schemas["Drive"] }) {
  if (!drive.job_description) return null;
  return (
    <Card>
      <CardHeader title="Job description" />
      <CardBody>
        <pre className="font-sans text-sm whitespace-pre-wrap text-muted">{drive.job_description}</pre>
      </CardBody>
    </Card>
  );
}
