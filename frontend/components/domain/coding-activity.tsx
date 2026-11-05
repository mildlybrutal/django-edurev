"use client";

import { CodeXml, ExternalLink, GitBranch, RefreshCw, Trophy } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { TextField } from "@/components/ui/field";
import { FormError } from "@/components/ui/form";
import { Meter } from "@/components/ui/meter";
import { errorMessage, QueryState } from "@/components/ui/states";
import { VerificationBadge } from "@/components/ui/status";
import {
  CODEFORCES_HANDLE,
  GITHUB_USERNAME,
  handleFrom,
  LEETCODE_USERNAME,
  useCoding,
  useRefreshCoding,
  useSaveCoding,
  type CodingProfile,
} from "@/lib/api/profile-extras";
import { cn } from "@/lib/cn";

const PLATFORM = {
  github: { Icon: GitBranch, hue: "bg-mod-cobalt-soft text-mod-cobalt" },
  leetcode: { Icon: CodeXml, hue: "bg-mod-marigold-soft text-mod-marigold-text" },
  codeforces: { Icon: Trophy, hue: "bg-mod-teal-soft text-mod-teal" },
} as const;

function statusTone(status: CodingProfile["status"]) {
  return status === "ok" ? "success" : status === "pending" ? "info" : status === "not_found" ? "danger" : "warning";
}

function headline(p: CodingProfile): string {
  const s = p.stats as Record<string, number | null | undefined>;
  if (p.platform === "github") {
    return `${s.original_repos ?? 0} original repos · ${s.recent_push_events ?? 0} pushes in 90 days · ${s.stars ?? 0} stars`;
  }
  if (p.platform === "codeforces") {
    return `${s.solved_total ?? 0} solved · ${s.solved_1600_plus ?? 0} rated 1600+ · ${s.contests_attended ?? 0} contests${
      s.rating ? ` · rating ${s.rating}` : " · unrated"
    }`;
  }
  return `${s.solved_total ?? 0} solved (${s.solved_easy ?? 0} easy · ${s.solved_medium ?? 0} medium · ${s.solved_hard ?? 0} hard)${
    s.contest_rating ? ` · contest ${s.contest_rating}` : ""
  }`;
}

function PlatformRow({ profile }: { profile: CodingProfile }) {
  const [open, setOpen] = useState(false);
  const { Icon, hue } = PLATFORM[profile.platform];
  const url = (profile.stats.profile_url as string | undefined) ?? undefined;
  const parts = profile.explanation.components ?? [];
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-3">
        <span aria-hidden="true" className={cn("inline-flex size-9 items-center justify-center rounded-md", hue)}>
          <Icon className="size-[18px]" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
            {profile.platform_label}
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 text-muted hover:text-primary"
              >
                @{profile.username}
                <ExternalLink aria-hidden="true" className="size-3" />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : (
              <span className="text-muted">@{profile.username}</span>
            )}
            <Badge tone={statusTone(profile.status)}>{profile.status_label}</Badge>
            {profile.verification_status && <VerificationBadge status={profile.verification_status} />}
          </p>
          {profile.status === "ok" && <p className="mt-0.5 truncate text-xs text-muted">{headline(profile)}</p>}
          {profile.status !== "ok" && profile.error && <p className="mt-0.5 text-xs text-danger">{profile.error}</p>}
        </div>
        <p className="text-2xl font-semibold tabular-nums">
          {profile.score === null ? "—" : Math.round(profile.score)}
          <span className="text-sm font-normal text-muted">/100</span>
        </p>
      </div>
      {parts.length > 0 && (
        <>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="mt-2 text-xs font-medium text-primary hover:underline"
          >
            {open ? "Hide how this is rated" : "How this is rated"}
          </button>
          {open && (
            <div className="mt-2 animate-fade-in rounded-md bg-surface-muted px-3 py-2.5">
              {profile.explanation.summary && <p className="mb-2 text-xs text-muted">{profile.explanation.summary}</p>}
              <ul className="space-y-1.5">
                {parts.map((c) => (
                  <li key={c.key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-xs">
                    <span>
                      {c.label}: <span className="tabular-nums">{c.value}</span>
                      <span className="text-muted"> (full marks at {c.cap})</span>
                    </span>
                    <span className="text-right tabular-nums">
                      {c.points} / {Math.round(c.weight * 100)}
                    </span>
                    <Meter value={(c.points / (c.weight * 100)) * 100} label={c.label} className="col-span-2 h-1.5" />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </li>
  );
}

/**
 * GitHub / LeetCode / Codeforces ratings for a student. `editable` (the student themself) adds handle
 * editing and a manual refresh. Ratings are unverified external evidence.
 */
export function CodingActivityCard({
  student = "me",
  editable = false,
}: {
  student?: string | number;
  editable?: boolean;
}) {
  const coding = useCoding(student);
  const refresh = useRefreshCoding();
  const [editing, setEditing] = useState(false);
  return (
    <Card>
      <CardHeader
        title="Coding activity"
        description="GitHub, LeetCode and Codeforces, rated from public activity. Supporting evidence, not proof of expertise."
        action={
          editable &&
          coding.data &&
          coding.data.profiles.length > 0 && (
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => refresh.mutate()}
                disabled={refresh.isPending}
                aria-label="Sync coding profiles now"
              >
                <RefreshCw aria-hidden="true" className={cn("size-4", refresh.isPending && "animate-spin")} />
                Sync
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setEditing((e) => !e)}>
                {editing ? "Cancel" : "Edit"}
              </Button>
            </div>
          )
        }
      />
      <CardBody>
        <QueryState query={coding}>
          {(data) => {
            const showForm = editable && (editing || data.profiles.length === 0);
            return (
              <>
                {data.profiles.length > 0 && (
                  <div className="mb-4 flex items-end justify-between gap-4 rounded-md bg-surface-muted px-4 py-3">
                    <div>
                      <p className="text-xs text-muted">Coding activity score (readiness dimension)</p>
                      <p className="text-3xl font-semibold tabular-nums">
                        {data.coding_activity === null ? "—" : `${Math.round(data.coding_activity)}%`}
                      </p>
                    </div>
                    <p className="max-w-56 text-right text-xs text-muted">Mean of the synced platform ratings.</p>
                  </div>
                )}
                {data.profiles.length > 0 && (
                  <ul className="divide-y divide-border">
                    {data.profiles.map((p) => (
                      <PlatformRow key={p.id} profile={p} />
                    ))}
                  </ul>
                )}
                {data.profiles.length === 0 && !editable && (
                  <p className="text-sm text-muted">No coding profiles linked yet.</p>
                )}
                {showForm && (
                  <CodingForm
                    initial={data.profiles}
                    onDone={() => setEditing(false)}
                    className={data.profiles.length ? "mt-4 border-t border-border pt-4" : ""}
                  />
                )}
                {data.profiles.some((p) => p.platform === "leetcode") && (
                  <p className="mt-3 text-xs text-muted">LeetCode figures come from an unofficial public source.</p>
                )}
              </>
            );
          }}
        </QueryState>
      </CardBody>
    </Card>
  );
}

export function CodingForm({
  initial,
  onDone,
  className,
}: {
  initial: CodingProfile[];
  onDone?: () => void;
  className?: string;
}) {
  const save = useSaveCoding();
  const [github, setGithub] = useState(initial.find((p) => p.platform === "github")?.username ?? "");
  const [leetcode, setLeetcode] = useState(initial.find((p) => p.platform === "leetcode")?.username ?? "");
  const [codeforces, setCodeforces] = useState(initial.find((p) => p.platform === "codeforces")?.username ?? "");
  const gh = handleFrom(github, "github.com");
  const lc = handleFrom(leetcode, "leetcode.com");
  const cf = handleFrom(codeforces, "codeforces.com");
  const ghError = gh && !GITHUB_USERNAME.test(gh) ? "Use your GitHub username, e.g. ada-lovelace." : undefined;
  const lcError =
    lc && !LEETCODE_USERNAME.test(lc) ? "Use your LeetCode username (letters, numbers, - and _)." : undefined;
  const cfError =
    cf && !CODEFORCES_HANDLE.test(cf) ? "Use your Codeforces handle (3–24 letters, numbers, _ . -)." : undefined;
  const invalid = !!(ghError || lcError || cfError);
  return (
    <form
      className={cn("grid gap-4 sm:grid-cols-2", className)}
      onSubmit={(e) => {
        e.preventDefault();
        if (invalid) return;
        save.mutate({ github: gh, leetcode: lc, codeforces: cf }, { onSuccess: () => onDone?.() });
      }}
    >
      <TextField
        label="GitHub username"
        placeholder="ada-lovelace"
        autoComplete="off"
        spellCheck={false}
        value={github}
        error={ghError}
        onChange={(e) => setGithub(e.target.value)}
      />
      <TextField
        label="LeetCode username"
        placeholder="ada_codes"
        autoComplete="off"
        spellCheck={false}
        value={leetcode}
        error={lcError}
        onChange={(e) => setLeetcode(e.target.value)}
      />
      <TextField
        label="Codeforces handle"
        placeholder="ada_cf"
        autoComplete="off"
        spellCheck={false}
        value={codeforces}
        error={cfError}
        onChange={(e) => setCodeforces(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={save.isPending || invalid}>
          {save.isPending ? "Saving…" : "Save and sync"}
        </Button>
        <p className="text-xs text-muted">You can paste a profile link; leave a field empty to unlink it.</p>
      </div>
      {save.isError && (
        <div className="sm:col-span-2">
          <FormError message={errorMessage(save.error)} />
        </div>
      )}
    </form>
  );
}
