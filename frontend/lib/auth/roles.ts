export const ROLES = ["student", "faculty", "placement_officer", "placement_head", "recruiter", "admin"] as const;

export type Role = (typeof ROLES)[number];

export type Portal = "student" | "faculty" | "placement";

/** Which internal portal each role lands in. Recruiters use the separate recruiter portal. */
export const PORTAL_ROLES: Record<Portal, readonly Role[]> = {
  student: ["student"],
  faculty: ["faculty"],
  placement: ["placement_officer", "placement_head", "admin"],
};

export function homeFor(roles: readonly string[]): string {
  if (roles.includes("recruiter")) return "/recruiter/login";
  for (const portal of ["placement", "faculty", "student"] as const) {
    if (PORTAL_ROLES[portal].some((r) => roles.includes(r))) return `/${portal}`;
  }
  return "/login";
}

export function canUsePortal(roles: readonly string[], portal: Portal): boolean {
  return PORTAL_ROLES[portal].some((r) => roles.includes(r));
}

/** The internal portal a user belongs to, or null for recruiters / users without a role. */
export function portalFor(roles: readonly string[]): Portal | null {
  for (const portal of ["placement", "faculty", "student"] as const) {
    if (PORTAL_ROLES[portal].some((r) => roles.includes(r))) return portal;
  }
  return null;
}
