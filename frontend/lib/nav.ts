import {
  BriefcaseBusiness,
  CalendarCheck,
  ChartColumn,
  ClipboardCheck,
  ClipboardList,
  FileText,
  KeyRound,
  Layers,
  LayoutDashboard,
  type LucideIcon,
  Network,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  UserRound,
  Users,
} from "lucide-react";
import type { Portal, Role } from "@/lib/auth/roles";

export type NavItem = { href: string; label: string; icon: LucideIcon; roles?: readonly Role[] };

/** Navigation per portal (AGENTS.md §12). `roles` narrows an item within a portal. */
export const NAV: Record<Portal, { title: string; items: NavItem[] }> = {
  student: {
    title: "Student",
    items: [
      { href: "/student", label: "Dashboard", icon: LayoutDashboard },
      { href: "/student/profile", label: "My Profile", icon: UserRound },
      { href: "/student/evidence", label: "Skills & Evidence", icon: Layers },
      { href: "/student/drives", label: "Placement Drives", icon: BriefcaseBusiness },
      { href: "/student/assessments", label: "Assessments", icon: ClipboardCheck },
      { href: "/student/plan", label: "Preparation Plan", icon: CalendarCheck },
      { href: "/student/progress", label: "Progress", icon: TrendingUp },
    ],
  },
  faculty: {
    title: "Faculty",
    items: [
      { href: "/faculty", label: "Dashboard", icon: LayoutDashboard },
      { href: "/faculty/verification", label: "Verification Queue", icon: ShieldCheck },
      { href: "/faculty/assessments", label: "Assessments & Mock Interviews", icon: ClipboardList },
      { href: "/faculty/students", label: "My Students", icon: Users },
    ],
  },
  placement: {
    title: "Placement Cell",
    items: [
      { href: "/placement", label: "Dashboard", icon: LayoutDashboard },
      { href: "/placement/drives", label: "Placement Drives", icon: BriefcaseBusiness },
      { href: "/placement/students", label: "Students", icon: Users },
      { href: "/placement/analytics", label: "Batch Analytics", icon: ChartColumn },
      { href: "/placement/reports", label: "Reports", icon: FileText },
      {
        href: "/placement/skills",
        label: "Manage Skills",
        icon: Network,
        roles: ["placement_officer", "placement_head", "admin"],
      },
      { href: "/placement/recruiter-access", label: "Recruiter Access", icon: KeyRound, roles: ["placement_head"] },
      {
        href: "/placement/settings",
        label: "Scoring & Rubrics",
        icon: SlidersHorizontal,
        roles: ["admin", "placement_officer", "placement_head"],
      },
    ],
  },
};
