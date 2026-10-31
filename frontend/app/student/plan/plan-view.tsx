"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ExternalLink, Flag } from "lucide-react";
import { PlanCalendar } from "@/components/charts/calendar";
import { TimeBudget } from "@/components/domain/time-budget";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { ModuleRow, NextTag } from "@/components/ui/module-spine";
import { QueryState } from "@/components/ui/states";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { patch } from "@/lib/api/request";
import { cn } from "@/lib/cn";

type Plan = Schemas["Plan"];
type Item = Schemas["PlanItem"];

export function PlanView() {
  const params = useSearchParams();
  const plans = useQuery({
    queryKey: ["plans", "active"],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/preparation-plans/", { params: { query: { status: "active" } } })).results,
  });
  const selectedId = Number(params.get("plan")) || plans.data?.[0]?.id;

  return (
    <>
      <PageHeader
        title="Preparation Plan"
        description="Dated tasks and checkpoints built from your highest-impact skill gaps."
      />
      <QueryState query={plans}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No active plan">
              Open a{" "}
              <Link className="text-primary" href="/student/drives">
                placement drive
              </Link>{" "}
              and create a plan from its gaps.
            </EmptyState>
          ) : (
            <div className="flex flex-col gap-5">
              {list.length > 1 && (
                <nav aria-label="Plans" className="flex flex-wrap gap-2">
                  {list.map((p) => (
                    <Link
                      key={p.id}
                      href={`/student/plan?plan=${p.id}`}
                      aria-current={p.id === selectedId ? "page" : undefined}
                      className={cn(
                        "rounded-full border px-3 py-1 text-sm transition-colors duration-150",
                        p.id === selectedId
                          ? "border-primary bg-primary-soft text-primary"
                          : "border-border hover:border-border-strong",
                      )}
                    >
                      {p.title}
                    </Link>
                  ))}
                </nav>
              )}
              {selectedId && <PlanDetail id={selectedId} />}
            </div>
          )
        }
      </QueryState>
    </>
  );
}

function PlanDetail({ id }: { id: number }) {
  const queryClient = useQueryClient();
  const plan = useQuery({
    queryKey: ["plan", id],
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/preparation-plans/{plan_id}/", { params: { path: { plan_id: id } } })),
  });
  const update = useMutation({
    meta: { toast: (v: never) => ((v as { status: string }).status === "done" ? "Task done" : "Task reopened") },
    mutationFn: ({ item, status }: { item: Item; status: string }) =>
      patch(`/api/v1/preparation-plans/items/${item.id}/`, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan", id] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
  return (
    <QueryState query={plan}>
      {(p) => (
        <PlanBody
          plan={p}
          onToggle={(item) => update.mutate({ item, status: item.status === "done" ? "todo" : "done" })}
          busy={update.isPending}
        />
      )}
    </QueryState>
  );
}

function PlanBody({ plan, onToggle, busy }: { plan: Plan; onToggle: (item: Item) => void; busy: boolean }) {
  const progress = plan.progress as { total: number; done: number; overdue: number; percent: number };
  const today = new Date().toISOString().slice(0, 10);
  const items = [...plan.items].sort((a, b) => a.due_date.localeCompare(b.due_date) || a.order - b.order);
  const nextId = items.find((i) => i.status !== "done")?.id;
  return (
    <div className="flex flex-col gap-5">
      <TimeBudget
        start={plan.start_date}
        end={plan.end_date}
        driveDate={plan.drive_date}
        company={plan.company}
        done={progress.done}
        total={progress.total}
      />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 2xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title={plan.title}
            description={`${plan.start_date} → ${plan.end_date}${progress.overdue ? ` · ${progress.overdue} overdue` : ""}`}
            action={
              plan.drive_id ? (
                <Link href={`/student/drives/${plan.drive_id}`} className="text-sm text-primary hover:underline">
                  View drive
                </Link>
              ) : undefined
            }
          />
          <CardBody>
            <ol className="flex flex-col gap-2.5">
              {items.map((item, index) => {
                const done = item.status === "done";
                const overdue = !done && item.due_date < today;
                const next = item.id === nextId;
                return (
                  <li key={item.id}>
                    <ModuleRow index={index + 1} cluster={item.cluster} next={next} done={done}>
                      <div className="flex gap-3">
                        <input
                          type="checkbox"
                          className="mt-0.5 size-4 shrink-0 cursor-pointer"
                          checked={done}
                          disabled={busy}
                          onChange={() => onToggle(item)}
                          aria-label={`Mark "${item.title}" as ${done ? "not done" : "done"}`}
                        />
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="flex flex-wrap items-center gap-2">
                            <span className={cn("font-medium", done && "text-muted line-through")}>{item.title}</span>
                            {next && <NextTag />}
                            {item.is_checkpoint && (
                              <Badge tone="info">
                                <Flag aria-hidden="true" className="size-3.5" />
                                Checkpoint
                              </Badge>
                            )}
                          </p>
                          {item.description && <p className="mt-0.5 text-muted">{item.description}</p>}
                          {item.resource_title &&
                            (item.resource_url ? (
                              <a
                                href={item.resource_url}
                                target="_blank"
                                rel="noreferrer noopener"
                                className="mt-1 inline-flex items-center gap-1 text-primary hover:underline"
                              >
                                {item.resource_title}
                                <ExternalLink aria-hidden="true" className="size-3" />
                              </a>
                            ) : (
                              <p className="mt-1">{item.resource_title}</p>
                            ))}
                          <p
                            className={cn(
                              "mt-1 text-xs tabular-nums",
                              overdue ? "font-medium text-danger" : "text-muted",
                            )}
                          >
                            {item.start_date} → {item.due_date}
                            {overdue && " · overdue"}
                          </p>
                        </div>
                      </div>
                    </ModuleRow>
                  </li>
                );
              })}
            </ol>
          </CardBody>
        </Card>
        <Card className="self-start">
          <CardHeader title="Calendar" />
          <CardBody>
            <PlanCalendar
              initialMonth={plan.start_date}
              items={items.map((i) => ({
                id: i.id,
                date: i.due_date,
                title: i.title,
                done: i.status === "done",
                checkpoint: !!i.is_checkpoint,
              }))}
            />
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
