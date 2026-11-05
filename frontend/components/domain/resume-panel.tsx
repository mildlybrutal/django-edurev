"use client";

import { Eye, FileText, FileUp, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { FormError } from "@/components/ui/form";
import { errorMessage, QueryState } from "@/components/ui/states";
import { get } from "@/lib/api/request";
import { resumeProblem, useDeleteResume, useResume, useUploadResume, type Resume } from "@/lib/api/profile-extras";
import { cn } from "@/lib/cn";

function size(bytes: number) {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * Opens the resume in a dialog. The link is short-lived and fetched fresh on every open, so a
 * stale link never reaches the viewer. `path` lets the recruiter portal use its own endpoint.
 */
export function ResumeViewerButton({
  path,
  label = "View resume",
  variant = "secondary",
  docLabel = "Resume",
  frameTitle = "Resume PDF",
}: {
  path: string;
  label?: string;
  variant?: "secondary" | "ghost" | "primary";
  /** What the dialog is showing; certificates reuse this viewer. */
  docLabel?: string;
  frameTitle?: string;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [state, setState] = useState<{ url?: string; error?: string; loading?: boolean }>({});
  const open = async () => {
    setState({ loading: true });
    dialog.current?.showModal();
    try {
      const r = await get<Pick<Resume, "url"> & { name?: string }>(path);
      setState({ url: r.url });
    } catch (e) {
      setState({ error: errorMessage(e) });
    }
  };
  return (
    <>
      <Button variant={variant} size="sm" onClick={open}>
        <Eye aria-hidden="true" className="size-4" />
        {label}
      </Button>
      <dialog
        ref={dialog}
        aria-label={docLabel}
        onClose={() => setState({})}
        className="m-auto h-[min(90vh,1000px)] w-[min(92vw,900px)] max-w-none overflow-hidden rounded-xl border border-border bg-surface p-0 text-foreground shadow-pop"
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
            <p className="flex items-center gap-2 text-sm font-medium">
              <FileText aria-hidden="true" className="size-4 text-muted" />
              {docLabel}
            </p>
            <div className="flex items-center gap-2">
              {state.url && (
                <a
                  href={state.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-sm text-primary hover:underline"
                >
                  Open in new tab
                </a>
              )}
              <button
                type="button"
                onClick={() => dialog.current?.close()}
                aria-label={`Close ${docLabel.toLowerCase()}`}
                className="rounded-md p-1.5 text-muted hover:bg-surface-muted hover:text-foreground"
              >
                <X aria-hidden="true" className="size-4" />
              </button>
            </div>
          </div>
          <div className="flex-1 bg-surface-muted">
            {state.loading && <p className="p-6 text-sm text-muted">Fetching a secure link…</p>}
            {state.error && (
              <div className="p-6">
                <FormError message={state.error} />
              </div>
            )}
            {state.url && <iframe src={state.url} title={frameTitle} className="h-full w-full border-0" />}
          </div>
        </div>
      </dialog>
    </>
  );
}

/** Drop zone + file input. Used in the onboarding dialog and on the profile page. */
export function ResumeDrop({ onFile, file }: { onFile: (f: File | null) => void; file?: File | null }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const problem = file ? resumeProblem(file) : null;
  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          onFile(e.dataTransfer.files[0] ?? null);
        }}
        className={cn(
          "flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-4 py-4 transition-colors duration-150",
          over ? "border-primary bg-primary-soft" : "border-border-strong hover:border-primary hover:bg-surface-muted",
        )}
      >
        <span
          aria-hidden="true"
          className="inline-flex size-9 items-center justify-center rounded-md bg-primary-soft text-primary"
        >
          <FileUp className="size-[18px]" strokeWidth={1.75} />
        </span>
        <span className="min-w-0 flex-1 text-sm">
          {file ? (
            <>
              <span className="block truncate font-medium">{file.name}</span>
              <span className="text-xs text-muted">{size(file.size)}</span>
            </>
          ) : (
            <>
              <span className="block font-medium">Choose a PDF or drop it here</span>
              <span className="text-xs text-muted">PDF only, up to 5 MB</span>
            </>
          )}
        </span>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
      </label>
      {problem && <p className="mt-1.5 text-sm text-danger">{problem}</p>}
    </div>
  );
}

export function ResumeCard({ student = "me", editable = false }: { student?: string | number; editable?: boolean }) {
  const resume = useResume(student);
  const uploadResume = useUploadResume();
  const remove = useDeleteResume();
  const [file, setFile] = useState<File | null>(null);
  const [replacing, setReplacing] = useState(false);
  const base = `/api/v1/students/${student}/resume/`;
  return (
    <Card>
      <CardHeader
        title="Resume"
        description={
          editable
            ? "Visible to your mentor and the placement cell, and to a recruiter only if the cell releases it."
            : undefined
        }
      />
      <CardBody>
        <QueryState query={resume}>
          {(r) => (
            <>
              {r ? (
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    aria-hidden="true"
                    className="inline-flex size-9 items-center justify-center rounded-md bg-mod-crimson-soft text-mod-crimson"
                  >
                    <FileText className="size-[18px]" strokeWidth={1.75} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{r.name}</p>
                    <p className="text-xs text-muted">
                      {size(r.size)} · uploaded {new Date(r.uploaded_at).toLocaleDateString()}
                    </p>
                  </div>
                  <ResumeViewerButton path={base} />
                  {editable && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => setReplacing((v) => !v)}>
                        {replacing ? "Cancel" : "Replace"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label="Delete resume"
                        disabled={remove.isPending}
                        onClick={() => {
                          if (window.confirm("Delete your resume? Staff will no longer be able to view it."))
                            remove.mutate();
                        }}
                      >
                        <Trash2 aria-hidden="true" className="size-4" />
                      </Button>
                    </>
                  )}
                </div>
              ) : (
                !editable && <p className="text-sm text-muted">No resume uploaded.</p>
              )}
              {editable && (!r || replacing) && (
                <form
                  className={cn("space-y-3", r && "mt-4 border-t border-border pt-4")}
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (file && !resumeProblem(file))
                      uploadResume.mutate(file, {
                        onSuccess: () => {
                          setFile(null);
                          setReplacing(false);
                        },
                      });
                  }}
                >
                  <ResumeDrop file={file} onFile={setFile} />
                  <Button type="submit" disabled={!file || !!resumeProblem(file) || uploadResume.isPending}>
                    {uploadResume.isPending ? "Uploading…" : "Upload resume"}
                  </Button>
                  {uploadResume.isError && <FormError message={errorMessage(uploadResume.error)} />}
                </form>
              )}
              {remove.isError && <FormError message={errorMessage(remove.error)} />}
            </>
          )}
        </QueryState>
      </CardBody>
    </Card>
  );
}
