"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CodeXml, GitBranch, Link2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { FormError } from "@/components/ui/form";
import { errorMessage } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import {
  GITHUB_USERNAME,
  handleFrom,
  LEETCODE_USERNAME,
  resumeProblem,
  type Onboarding,
} from "@/lib/api/profile-extras";
import { get, patch, post, upload } from "@/lib/api/request";
import { ResumeDrop } from "./resume-panel";

const LATER_KEY = "onboarding-later";

function laterThisSession() {
  try {
    return sessionStorage.getItem(LATER_KEY) === "1";
  } catch {
    return false;
  }
}

function Row({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="flex items-end gap-3">
      <span
        aria-hidden="true"
        className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-surface-muted text-muted"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/**
 * First-run pop-up for a student: link GitHub, LeetCode and LinkedIn and upload a resume.
 * Shown once per account until saved; "Later" hides it for this browser session only.
 */
export function OnboardingDialog() {
  const dialog = useRef<HTMLDialogElement>(null);
  const qc = useQueryClient();
  const push = useToast();
  const status = useQuery({
    queryKey: ["onboarding"],
    queryFn: () => get<Onboarding>("/api/v1/students/me/onboarding/"),
    staleTime: Infinity,
  });
  const [github, setGithub] = useState("");
  const [leetcode, setLeetcode] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (status.data?.required && !laterThisSession() && !dialog.current?.open) dialog.current?.showModal();
  }, [status.data]);

  const gh = handleFrom(github, "github.com");
  const lc = handleFrom(leetcode, "leetcode.com");
  const ghError = gh && !GITHUB_USERNAME.test(gh) ? "Use your GitHub username, e.g. ada-lovelace." : undefined;
  const lcError = lc && !LEETCODE_USERNAME.test(lc) ? "Use your LeetCode username." : undefined;
  const liError =
    linkedin && !/^https:\/\/([a-z]{2,3}\.)?linkedin\.com\/in\/[^/\s]+\/?$/i.test(linkedin.trim())
      ? "Paste your profile link, e.g. https://www.linkedin.com/in/your-name"
      : undefined;
  const fileError = file ? resumeProblem(file) : null;
  const invalid = !!(ghError || lcError || liError || fileError);

  const later = () => {
    try {
      sessionStorage.setItem(LATER_KEY, "1");
    } catch {
      // Storage blocked: it simply shows again next time.
    }
    dialog.current?.close();
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (gh || lc) await post("/api/v1/students/me/coding/", { github_username: gh, leetcode_username: lc });
      const links: Record<string, string> = {};
      if (gh) links.github_url = `https://github.com/${gh}`;
      if (linkedin) links.linkedin_url = linkedin.trim();
      if (Object.keys(links).length) await patch("/api/v1/students/me/", links);
      if (file) {
        const form = new FormData();
        form.append("file", file);
        await upload("/api/v1/students/me/resume/", form);
      }
      await post("/api/v1/students/me/onboarding/");
      await Promise.all(
        ["onboarding", "coding", "resume", "profile", "dashboard", "evidence", "student"].map((k) =>
          qc.invalidateQueries({ queryKey: [k] }),
        ),
      );
      dialog.current?.close();
      push({
        tone: "success",
        title: "Profile set up",
        body: gh || lc ? "Your coding activity is syncing; ratings appear in a moment." : undefined,
      });
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <dialog
      ref={dialog}
      aria-labelledby="onboarding-title"
      onCancel={(e) => {
        e.preventDefault();
        later();
      }}
      className="m-auto w-[min(92vw,560px)] max-w-none rounded-xl border border-border bg-surface p-0 text-foreground shadow-pop"
    >
      <form
        method="dialog"
        onSubmit={(e) => {
          e.preventDefault();
          if (!invalid) void save();
        }}
      >
        <div className="border-b border-border px-6 pt-6 pb-4">
          <h2 id="onboarding-title" className="text-lg font-semibold tracking-tight">
            Complete your placement profile
          </h2>
          <p className="mt-1 text-sm text-muted">
            Linked profiles and your resume become evidence for your readiness. Add what you have now; everything can be
            changed later from My Profile.
          </p>
        </div>
        <div className="max-h-[60vh] space-y-5 overflow-y-auto px-6 py-5">
          <Row icon={<GitBranch className="size-4" strokeWidth={1.75} />}>
            <TextField
              label="GitHub username"
              placeholder="ada-lovelace or a github.com link"
              autoComplete="off"
              spellCheck={false}
              value={github}
              error={ghError}
              onChange={(e) => setGithub(e.target.value)}
            />
          </Row>
          <Row icon={<CodeXml className="size-4" strokeWidth={1.75} />}>
            <TextField
              label="LeetCode username"
              placeholder="ada_codes or a leetcode.com link"
              autoComplete="off"
              spellCheck={false}
              value={leetcode}
              error={lcError}
              onChange={(e) => setLeetcode(e.target.value)}
            />
          </Row>
          <Row icon={<Link2 className="size-4" strokeWidth={1.75} />}>
            <TextField
              label="LinkedIn profile link"
              type="url"
              inputMode="url"
              placeholder="https://www.linkedin.com/in/your-name"
              value={linkedin}
              error={liError}
              onChange={(e) => setLinkedin(e.target.value)}
            />
          </Row>
          <div>
            <p className="mb-1.5 text-sm font-medium">Resume</p>
            <ResumeDrop file={file} onFile={setFile} />
          </div>
          <p className="text-xs text-muted">
            GitHub and LeetCode activity is rated from public data and counts as unverified supporting evidence, not
            proof of expertise. LeetCode data comes from an unofficial public source.
          </p>
          {error !== null && <FormError message={errorMessage(error)} />}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">
          <Button variant="ghost" onClick={later} disabled={saving}>
            Later
          </Button>
          <Button type="submit" disabled={saving || invalid}>
            {saving ? "Saving…" : "Save profile"}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
