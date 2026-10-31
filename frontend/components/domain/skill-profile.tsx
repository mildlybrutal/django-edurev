"use client";

import { ChevronDown, CircleCheck } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { VerificationBadge } from "@/components/ui/status";
import type { SkillClaim } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { HUE, hueFor } from "@/lib/modules";

/** Levelled skill claims; each expands to show the evidence behind it (AGENTS.md §4: never hide why). */
export function SkillProfileList({ claims }: { claims: SkillClaim[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (claims.length === 0) {
    return <EmptyState title="No skills yet">Skills appear here once evidence is tagged with them.</EmptyState>;
  }
  return (
    <ul className="divide-y divide-border">
      {claims.map((c) => {
        const expanded = open === c.skill_id;
        return (
          <li key={c.skill_id}>
            <button
              type="button"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : c.skill_id)}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 rounded-md px-2 py-3 text-left transition-colors duration-150 hover:bg-surface-muted sm:flex-nowrap"
            >
              <span className="flex w-full min-w-0 items-center gap-2 sm:w-48 sm:shrink-0">
                <span
                  aria-hidden="true"
                  className={cn("size-2.5 shrink-0 rounded-sm", HUE[hueFor(c.cluster_slug)].solid)}
                />
                <span className="truncate text-sm font-medium">{c.skill}</span>
              </span>
              <span className="flex flex-1 items-center gap-3">
                <LevelPips level={c.level} verified={c.verified_level} cluster={c.cluster_slug} />
                <span className="text-sm">{c.level_label}</span>
              </span>
              {c.is_verified ? (
                <Badge tone="success">
                  <CircleCheck aria-hidden="true" className="size-3.5" />
                  Verified
                </Badge>
              ) : c.verified_level > 0 ? (
                <Badge tone="warning">Verified to {c.verified_level_label}</Badge>
              ) : (
                <Badge>Unverified</Badge>
              )}
              <span className="flex items-center gap-1 text-xs whitespace-nowrap text-muted">
                {c.evidence.length} evidence
                <ChevronDown
                  aria-hidden="true"
                  className={cn("size-4 transition-transform duration-200 ease-out", expanded && "rotate-180")}
                />
              </span>
            </button>
            {expanded && (
              <ul className="mb-3 ml-1 flex animate-fade-in flex-col gap-2 rounded-md bg-surface-muted p-3">
                {c.evidence.map((e) => (
                  <li key={e.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <span className="font-medium">{e.title}</span>
                    <span className="text-muted">{e.source_label}</span>
                    <VerificationBadge status={e.verification_status} />
                    <span className="text-xs text-muted">
                      claims {e.claimed_level}
                      {e.claimed_level !== e.effective_level &&
                        ` · counted as ${e.effective_level} (evidence rule cap)`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Four pips for Beginner..Expert in the skill's module hue: solid = verified, outline =
 * claimed but unverified, track = not reached. */
export function LevelPips({ level, verified, cluster }: { level: number; verified: number; cluster?: string | null }) {
  const hue = HUE[hueFor(cluster)];
  return (
    <span className="flex gap-1" aria-hidden="true">
      {[1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={cn(
            "h-2.5 w-5 rounded-sm",
            i <= verified ? hue.solid : i <= level ? cn("border-2 bg-surface", hue.border) : "bg-surface-muted",
          )}
        />
      ))}
    </span>
  );
}
