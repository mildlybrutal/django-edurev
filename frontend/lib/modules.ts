/**
 * Module hues: each skill cluster owns one flat colour, like the colour-coded modules of a
 * coaching booklet. The `next` blue is never a module; it is reserved for "your next step".
 */
export type ModuleHue = "cobalt" | "teal" | "green" | "marigold" | "crimson";

const BY_CLUSTER: Record<string, ModuleHue> = {
  programming: "cobalt",
  backend: "cobalt",
  frontend: "cobalt",
  databases: "teal",
  devops: "teal",
  data: "green",
  testing: "marigold",
  "cs-fundamentals": "crimson",
};

const ORDER: ModuleHue[] = ["cobalt", "teal", "green", "marigold", "crimson"];

/** Clusters added later by an admin still get a stable hue. */
export function hueFor(cluster: string | null | undefined): ModuleHue {
  if (!cluster) return "cobalt";
  const known = BY_CLUSTER[cluster];
  if (known) return known;
  let h = 0;
  for (const ch of cluster) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return ORDER[h % ORDER.length];
}

/** Static class strings so Tailwind can see them. */
export const HUE: Record<
  ModuleHue,
  { solid: string; soft: string; text: string; ink: string; bar: string; border: string }
> = {
  cobalt: {
    solid: "bg-mod-cobalt",
    soft: "bg-mod-cobalt-soft",
    text: "text-mod-cobalt",
    ink: "text-mod-ink-light",
    bar: "bg-mod-cobalt",
    border: "border-mod-cobalt",
  },
  teal: {
    solid: "bg-mod-teal",
    soft: "bg-mod-teal-soft",
    text: "text-mod-teal",
    ink: "text-mod-ink-light",
    bar: "bg-mod-teal",
    border: "border-mod-teal",
  },
  green: {
    solid: "bg-mod-green",
    soft: "bg-mod-green-soft",
    text: "text-mod-green",
    ink: "text-mod-ink-light",
    bar: "bg-mod-green",
    border: "border-mod-green",
  },
  marigold: {
    solid: "bg-mod-marigold",
    soft: "bg-mod-marigold-soft",
    text: "text-mod-marigold-text",
    ink: "text-mod-ink-dark",
    bar: "bg-mod-marigold",
    border: "border-mod-marigold",
  },
  crimson: {
    solid: "bg-mod-crimson",
    soft: "bg-mod-crimson-soft",
    text: "text-mod-crimson",
    ink: "text-mod-ink-light",
    bar: "bg-mod-crimson",
    border: "border-mod-crimson",
  },
};
