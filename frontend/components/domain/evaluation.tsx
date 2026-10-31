"use client";

import { CircleCheck, CircleX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Meter } from "@/components/ui/meter";
import { ModuleRow, NextTag } from "@/components/ui/module-spine";
import { EligibilityBadge, ImpactBadge } from "@/components/ui/status";
import { Table, Td, Th } from "@/components/ui/table";
import type { Evaluation, Gap } from "@/lib/api/types";
import { ReadinessPanel } from "./readiness-panel";

/**
 * Eligibility, compatibility and readiness for one student and drive. They are separate cards
 * on purpose: eligibility is a hard yes/no on criteria; compatibility and readiness are evidence
 * scores. The UI must never merge them (P06 §2).
 */
export function EvaluationView({ evaluation, forStudent = false }: { evaluation: Evaluation; forStudent?: boolean }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <EligibilityCard evaluation={evaluation} />
      <CompatibilityCard evaluation={evaluation} />
      <Card className="xl:col-span-2">
        <CardHeader
          title="Readiness for this role"
          description="Technical mastery here is your skill match for this drive; the other dimensions come from your assessments and projects."
        />
        <CardBody>
          <ReadinessPanel snapshot={evaluation.readiness} threshold={evaluation.ready_threshold} />
        </CardBody>
      </Card>
      <Card className="xl:col-span-2">
        <CardHeader title="Skill gaps" description="Ranked by impact on your match for this drive." />
        <CardBody>
          <GapList gaps={evaluation.gaps} showNext={forStudent} />
        </CardBody>
      </Card>
    </div>
  );
}

export function EligibilityCard({ evaluation }: { evaluation: Evaluation }) {
  const { eligibility } = evaluation;
  return (
    <Card>
      <CardHeader
        title="Eligibility"
        description="Hard criteria set by the company. Independent of your skills."
        action={<EligibilityBadge eligible={eligibility.is_eligible} />}
      />
      <CardBody>
        {evaluation.academic_record_verified === false && (
          <p className="mb-3 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning">
            Based on self-declared CGPA and backlogs. The placement cell confirms them before shortlisting.
          </p>
        )}
        {eligibility.reasons.length === 0 ? (
          <p className="text-sm text-muted">This drive has no eligibility criteria.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {eligibility.reasons.map((r) => (
              <li key={r.rule} className="flex items-start gap-2">
                {r.passed ? (
                  <CircleCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                ) : (
                  <CircleX aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-danger" />
                )}
                <span>
                  <span className="font-medium">{r.required}</span>
                  <span className="text-muted">
                    {" "}
                    — {r.passed ? "met" : r.message} (yours: {r.actual})
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

export function CompatibilityCard({ evaluation }: { evaluation: Evaluation }) {
  const { compatibility } = evaluation;
  return (
    <Card>
      <CardHeader
        title="Skill compatibility"
        description="Your skill profile against this drive's requirements."
        action={<span className="text-2xl font-semibold tabular-nums">{compatibility.score.toFixed(0)}%</span>}
      />
      <Table caption="Requirement-by-requirement match">
        <thead>
          <tr>
            <Th>Required skill</Th>
            <Th>Required</Th>
            <Th>You</Th>
            <Th className="w-28">Credit</Th>
          </tr>
        </thead>
        <tbody>
          {compatibility.requirements.map((r) => (
            <tr key={r.skill_id}>
              <Td>
                <span className="font-medium">{r.skill}</span>
                {r.is_mandatory && <span className="ml-1.5 text-xs text-muted">mandatory</span>}
                {r.match === "taxonomy" && <span className="block text-xs text-muted">via {r.matched_skill}</span>}
              </Td>
              <Td>{r.required_label}</Td>
              <Td>
                {r.match === "none" ? (
                  <span className="text-muted">No evidence</span>
                ) : (
                  <>
                    {r.level_label}
                    {r.verified_level < r.level && (
                      <span className="block text-xs text-muted">verified: {r.verified_label}</span>
                    )}
                  </>
                )}
              </Td>
              <Td>
                <Meter value={r.credit * 100} label={`${r.skill} credit`} />
                <span className="text-xs tabular-nums text-muted">{Math.round(r.credit * 100)}%</span>
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

export function GapList({ gaps, showNext = false }: { gaps: Gap[]; showNext?: boolean }) {
  if (gaps.length === 0) {
    return <EmptyState title="No gaps">Your evidence meets every requirement of this drive.</EmptyState>;
  }
  return (
    <ol className="flex flex-col gap-2.5">
      {gaps.map((g) => {
        const next = showNext && g.rank === 1;
        return (
          <li key={g.skill_id}>
            <ModuleRow index={g.rank} cluster={g.cluster} next={next}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="sr-only">Rank {g.rank}:</span>
                <span className="font-medium">{g.skill}</span>
                {next && <NextTag>Start here</NextTag>}
                <ImpactBadge level={g.impact} />
                <Badge>{g.kind_label}</Badge>
                {g.is_mandatory && <Badge tone="primary">Mandatory</Badge>}
              </div>
              <p className="mt-1 text-sm text-muted tabular-nums">
                Current {g.current} · verified {g.verified} · required {g.required}
              </p>
              <p className="mt-1.5 text-sm">{g.suggested_action}</p>
            </ModuleRow>
          </li>
        );
      })}
    </ol>
  );
}
