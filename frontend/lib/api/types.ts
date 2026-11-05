/** Shapes of computed (non-model) API payloads. Kept in step with the backend services:
 * students/api/views.py, drives/api/views.py (evaluation_payload, _match_rows),
 * reporting/services.py and reporting/api/views.py. */

export type Dimensions = {
  technical: number;
  aptitude: number;
  communication: number;
  project_depth: number;
  /** GitHub / LeetCode ratings; absent on snapshots computed before the dimension existed. */
  coding_activity?: number;
};

export type DimensionExplanation = {
  score: number;
  summary: string;
  inputs: Record<string, unknown>[];
  missing: string | null;
};

export type Snapshot = Dimensions & {
  id: number;
  drive_id: number | null;
  created_at: string;
  config_version: number;
  overall: number;
  explanation: {
    config_version: number;
    weights: Record<keyof Dimensions, number>;
    ready_threshold: number;
    dimensions: Record<keyof Dimensions, DimensionExplanation>;
    note: string;
  };
};

export type StudentReadiness = {
  latest: Snapshot | null;
  ready_threshold: number;
  history: { at: string; overall: number }[];
};

export type ClaimEvidence = {
  id: number;
  title: string;
  source_type: string;
  source_label: string;
  verification_status: string;
  claimed_level: string;
  effective_level: string;
  verified: boolean;
};

export type SkillClaim = {
  skill_id: number;
  skill: string;
  cluster: string | null;
  cluster_slug?: string | null;
  level: number;
  level_label: string;
  verified_level: number;
  verified_level_label: string;
  is_verified: boolean;
  evidence: ClaimEvidence[];
};

export type SkillProfile = {
  student: import("./client").Schemas["Student"];
  completion: { percent: number; checks: { key: string; label: string; done: boolean }[] };
  claims: SkillClaim[];
};

export type EligibilityReason = { rule: string; passed: boolean; required: string; actual: string; message: string };

export type RequirementResult = {
  skill_id: number;
  skill: string;
  required_level: number;
  required_label: string;
  weight: number;
  is_mandatory: boolean;
  match: "exact" | "taxonomy" | "none";
  matched_skill: string | null;
  taxonomy_depth?: number;
  level: number;
  level_label: string;
  verified_level: number;
  verified_label: string;
  credit: number;
};

export type Gap = {
  rank: number;
  skill_id: number;
  skill: string;
  kind: "missing" | "below_level" | "unverified";
  kind_label: string;
  current: string;
  verified: string;
  required: string;
  is_mandatory: boolean;
  impact: "high" | "medium" | "low";
  impact_score: number;
  suggested_action: string;
  cluster?: string | null;
};

export type Evaluation = {
  drive_id: number;
  /** False while CGPA/backlogs are self-declared at sign-up and not yet confirmed by the cell. */
  academic_record_verified?: boolean;
  eligibility: { is_eligible: boolean; reasons: EligibilityReason[]; computed_at: string };
  compatibility: { score: number; requirements: RequirementResult[]; computed_at: string };
  readiness: Snapshot | null;
  is_ready: boolean;
  ready_threshold: number;
  gaps: Gap[];
  registration: { id: number; status: string } | null;
  registration_open: boolean;
  plan_id: number | null;
};

export type StudentDashboard = {
  student: { name: string; roll_number: string; department: string };
  cards: {
    profile_completion: number;
    verified_evidence: number;
    total_evidence: number;
    eligible_drives: number;
    readiness: number | null;
  };
  readiness: (Dimensions & { overall: number }) | null;
  skills: {
    skill: string;
    level: number;
    level_label: string;
    percent: number;
    is_verified: boolean;
    verified_level: number;
    cluster: string | null;
  }[];
  drives: {
    id: number;
    company: string;
    role: string;
    drive_date: string | null;
    status: string;
    is_eligible: boolean;
    compatibility: number;
    readiness: number | null;
    is_ready: boolean;
    registration: { id: number; status: string } | null;
    top_gaps: Gap[];
  }[];
  tasks: {
    id: number;
    title: string;
    due_date: string;
    is_checkpoint: boolean;
    overdue: boolean;
    status: string;
    skill: string | null;
    cluster: string | null;
    plan_id: number;
  }[];
  plan: {
    id: number;
    title: string;
    company: string | null;
    start_date: string;
    end_date: string;
    drive_date: string | null;
    days_left: number;
    total_days: number;
    total: number;
    done: number;
  } | null;
  activity: { title: string; at: string; link: string }[];
};

export type StudentSummary = {
  id: number;
  name: string;
  email: string;
  roll_number: string;
  department: string;
  graduation_year: number;
  cgpa: number;
  active_backlogs: number;
  academic_record_verified: boolean;
  mentor: string | null;
  readiness: number | null;
  evidence_total: number;
  evidence_verified: number;
  evidence_pending: number;
  evidence_rejected: number;
  registrations: number;
  eligible_drives: number;
  plan_done: number;
  plan_total: number;
};

export type FacultyDashboard = {
  mentees: number;
  pending_verifications: number;
  students: StudentSummary[];
};

/** GET /students/:id/drives — eligibility and compatibility/readiness are separate fields. */
export type StudentDriveRow = {
  drive_id: number;
  company: string;
  role: string;
  drive_date: string | null;
  drive_status: string;
  registration_status: string;
  registered_at: string;
  is_eligible: boolean | null;
  failed_rules: { rule: string; message: string }[];
  compatibility: number | null;
  readiness: number | null;
  plan: { id: number; done: number; total: number } | null;
};

export type Band = { band: string; count: number; percent: number };

export type GapFrequencyRow = {
  skill_id: number;
  skill: string;
  students: number;
  high_impact: number;
  missing: number;
  unverified: number;
  cluster?: string | null;
};

export type Overview = {
  total_students: number;
  students_with_readiness: number;
  active_drives: number;
  eligible_students: number;
  average_readiness: number | null;
  readiness_distribution: Band[];
  recent_drives: {
    id: number;
    company: string;
    role: string;
    status: string;
    status_label: string;
    eligible: number;
    registered: number;
    average_compatibility: number | null;
    average_readiness: number | null;
    matched: boolean;
  }[];
  top_gaps: GapFrequencyRow[];
};

export type SupplyDemand = {
  drive_id: number;
  drive: string;
  population: "all" | "eligible";
  students: number;
  requirements: {
    skill_id: number;
    skill: string;
    required_level: string;
    is_mandatory: boolean;
    weight: number;
    demand_share: number;
    supply_percent: number;
    verified_supply_percent: number;
    any_evidence_percent: number;
    shortfall_students: number;
    cluster?: string | null;
  }[];
};

export type DemandAcrossDrives = {
  active_drives: number;
  students: number;
  skills: {
    skill_id: number;
    skill: string;
    active_drives: number;
    required_level: string;
    supply_percent: number;
    cluster?: string | null;
  }[];
};

export type VerificationCoverage = {
  total_evidence: number;
  by_status: Record<string, number>;
  by_source: { source_type: string; total: number; verified: number; percent_verified: number }[];
  students: number;
  students_with_verified_evidence: number;
  student_coverage_percent: number;
  pending: number;
};

export type Funnel = { drive_id: number; stages: { stage: string; count: number }[] };

export type DepartmentRow = {
  department: string;
  name: string;
  students: number;
  average_readiness: number | null;
  ready_percent: number | null;
};

export type TrainingEffectiveness = {
  students_with_history: number;
  average_change: number | null;
  plan_engaged: { students: number; average_change: number | null };
  not_engaged: { students: number; average_change: number | null };
  note: string;
};

export type MatchRow = {
  student_id: number;
  name: string;
  roll_number: string;
  department: string;
  cgpa: string;
  eligible: boolean | null;
  failed_criteria: string[];
  compatibility: number;
  readiness: number | null;
  registration_id: number | null;
  registration_status: string | null;
};

export type MatchList = {
  drive_id: number;
  last_matched_at: string | null;
  ready_threshold: number;
  summary: {
    evaluated: number;
    eligible: number;
    high_match: number;
    average_compatibility: number | null;
    registered: number;
  };
  results: MatchRow[];
};

export type JDExtraction = {
  method?: string;
  skills?: {
    skill_id: number;
    skill: string;
    matched_text: string;
    evidence: string;
    required_level: number;
    is_mandatory: boolean;
    weight: number;
  }[];
  eligibility?: { rule_type: string; value: unknown; label: string }[];
};

export type JDState = { status: string; text: string; extraction: JDExtraction };

export type Candidate = {
  id: number;
  name?: string;
  email?: string;
  department?: { code: string; name: string };
  graduation_year?: number;
  cgpa?: string;
  compatibility?: number | null;
  readiness?: (Dimensions & { overall: number }) | null;
  skills?: { skill: string; level: string; verified: boolean }[];
  evidence?: { title: string; type: string; verification: string }[];
  registration_status?: string | null;
  coding_activity?: { score: number | null; platforms: { platform: string; rating: number | null }[] };
  resume_available?: boolean;
};

export type CandidatePage = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Candidate[];
  facets: Record<string, { value: string; count: number }[]>;
  fields: string[];
};
