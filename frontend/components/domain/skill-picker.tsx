"use client";

import { useId, useState } from "react";
import { useSkills, type Skill } from "@/lib/api/taxonomy";

/** Search-as-you-type picker over the institution's taxonomy. */
export function SkillPicker({
  label,
  onPick,
  exclude = [],
  disabled,
}: {
  label: string;
  onPick: (skill: Skill) => void;
  exclude?: number[];
  disabled?: boolean;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const { data } = useSkills(query.trim(), "", 1);
  const results = query.trim() ? (data?.results ?? []).filter((s) => !exclude.includes(s.id)).slice(0, 6) : [];

  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="search"
        placeholder={label}
        value={query}
        disabled={disabled}
        onChange={(e) => setQuery(e.target.value)}
        className="h-8 w-full rounded-md border border-border bg-surface px-2.5 text-sm placeholder:text-muted"
        autoComplete="off"
      />
      {results.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-md border border-border bg-surface shadow-sm">
          {results.map((skill) => (
            <li key={skill.id}>
              <button
                type="button"
                className="block w-full px-3 py-1.5 text-left text-sm hover:bg-surface-muted"
                onClick={() => {
                  onPick(skill);
                  setQuery("");
                }}
              >
                {skill.name}
                {skill.cluster && <span className="ml-2 text-xs text-muted">{skill.cluster.name}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
