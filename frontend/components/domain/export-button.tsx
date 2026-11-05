"use client";

import { useMutation } from "@tanstack/react-query";
import { FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form";
import { errorMessage } from "@/components/ui/states";
import { download } from "@/lib/api/request";

/** Downloads a staff Excel export. `path` already carries the active filters. */
export function ExportButton({
  path,
  filename,
  label = "Export to Excel",
}: {
  path: string;
  filename: string;
  label?: string;
}) {
  const run = useMutation({ mutationFn: () => download(path, `${filename}.xlsx`) });
  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="secondary" size="sm" onClick={() => run.mutate()} disabled={run.isPending}>
        <FileSpreadsheet aria-hidden="true" className="size-4" />
        {run.isPending ? "Preparing…" : label}
      </Button>
      {run.error ? <FormError message={errorMessage(run.error)} /> : null}
    </div>
  );
}
