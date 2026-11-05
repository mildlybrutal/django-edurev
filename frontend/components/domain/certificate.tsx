"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form";
import { errorMessage } from "@/components/ui/states";
import type { Schemas } from "@/lib/api/client";
import { upload } from "@/lib/api/request";
import { ResumeViewerButton } from "./resume-panel";

type Evidence = Schemas["Evidence"];

export const CERTIFICATE_ACCEPT = ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg";
const MAX_BYTES = 5 * 1024 * 1024;

/** Client-side pre-check; the server re-validates by file content. */
export function certificateProblem(file: File): string | null {
  if (file.size > MAX_BYTES) return "Certificate must be 5 MB or smaller.";
  if (!/\.(pdf|png|jpe?g)$/i.test(file.name)) return "Upload a PDF, PNG or JPEG file.";
  return null;
}

export function uploadCertificate(evidenceId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  return upload<Evidence>(`/api/v1/evidence/${evidenceId}/certificate/`, form);
}

/** Opens the certificate through a short-lived signed link (each staff view is audited). */
export function CertificateViewButton({ item }: { item: Evidence }) {
  if (!item.certificate) return null;
  return (
    <ResumeViewerButton
      path={`/api/v1/evidence/${item.id}/certificate/`}
      label="View certificate"
      docLabel="Certificate"
      frameTitle="Certificate file"
      variant="ghost"
    />
  );
}

/** Upload or replace the file on the student's own certification evidence. */
export function CertificateUpload({ item }: { item: Evidence }) {
  const input = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const send = useMutation({
    meta: { toast: item.certificate ? "Certificate replaced" : "Certificate uploaded" },
    mutationFn: (file: File) => {
      const problem = certificateProblem(file);
      if (problem) throw new Error(problem);
      return uploadCertificate(item.id, file);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["evidence"] }),
  });
  return (
    <>
      <input
        ref={input}
        type="file"
        accept={CERTIFICATE_ACCEPT}
        className="sr-only"
        aria-label={`Certificate file for ${item.title}`}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) send.mutate(file);
          e.target.value = "";
        }}
      />
      <Button variant="secondary" onClick={() => input.current?.click()} disabled={send.isPending}>
        <FileUp aria-hidden="true" className="size-4" />
        {item.certificate ? "Replace certificate" : "Upload certificate"}
      </Button>
      {send.error ? <FormError message={errorMessage(send.error)} /> : null}
    </>
  );
}
