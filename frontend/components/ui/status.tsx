import { CircleCheck, CircleDashed, CircleDot, CircleX, Clock, type LucideIcon, TriangleAlert } from "lucide-react";
import { Badge, type Tone } from "./badge";

/* Status is always icon + label, never colour alone. */

const verification: Record<string, { tone: Tone; Icon: LucideIcon; label: string }> = {
  verified: { tone: "success", Icon: CircleCheck, label: "Verified" },
  pending: { tone: "warning", Icon: Clock, label: "Pending" },
  self_reported: { tone: "neutral", Icon: CircleDashed, label: "Self-reported" },
  rejected: { tone: "danger", Icon: CircleX, label: "Rejected" },
};

function Glyph({ Icon }: { Icon: LucideIcon }) {
  return <Icon aria-hidden="true" className="size-3.5" strokeWidth={2.25} />;
}

export function VerificationBadge({ status }: { status: string | null | undefined }) {
  const v = verification[status ?? "self_reported"] ?? verification.self_reported;
  return (
    <Badge tone={v.tone}>
      <Glyph Icon={v.Icon} />
      {v.label}
    </Badge>
  );
}

export function EligibilityBadge({ eligible }: { eligible: boolean | null | undefined }) {
  if (eligible === null || eligible === undefined) return <Badge>Not evaluated</Badge>;
  return eligible ? (
    <Badge tone="success">
      <Glyph Icon={CircleCheck} />
      Eligible
    </Badge>
  ) : (
    <Badge tone="danger">
      <Glyph Icon={CircleX} />
      Not eligible
    </Badge>
  );
}

export function ReadyBadge({ ready }: { ready: boolean }) {
  return ready ? (
    <Badge tone="success">
      <Glyph Icon={CircleDot} />
      Ready
    </Badge>
  ) : (
    <Badge tone="warning">
      <Glyph Icon={TriangleAlert} />
      Not yet ready
    </Badge>
  );
}

const impact: Record<string, Tone> = { high: "danger", medium: "warning", low: "neutral" };

export function ImpactBadge({ level }: { level: string }) {
  return <Badge tone={impact[level] ?? "neutral"}>{level[0]?.toUpperCase() + level.slice(1)} impact</Badge>;
}

const driveTone: Record<string, Tone> = {
  draft: "neutral",
  published: "primary",
  registration_closed: "info",
  shortlisting: "info",
  completed: "success",
  cancelled: "danger",
};

export function DriveStatusBadge({ status, label }: { status: string; label?: string }) {
  const text = label ?? status.replace(/_/g, " ");
  return <Badge tone={driveTone[status] ?? "neutral"}>{text[0].toUpperCase() + text.slice(1)}</Badge>;
}

export function RegistrationBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-sm text-muted">Not registered</span>;
  const tone: Tone =
    status === "selected" || status === "shortlisted"
      ? "success"
      : status === "withdrawn" || status.startsWith("not_")
        ? "neutral"
        : "primary";
  const label = status.replace(/_/g, " ");
  return <Badge tone={tone}>{label[0].toUpperCase() + label.slice(1)}</Badge>;
}
