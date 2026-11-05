---
name: Placement Readiness
description: Evidence-based placement readiness, laid out as numbered, colour-coded study modules.
colors:
  background: "light-dark(#f5f5f5, #141210)"
  surface: "light-dark(#ffffff, #1d1a17)"
  surface-muted: "light-dark(#f7f2ec, #26221e)"
  surface-raised: "light-dark(#ffffff, #231f1b)"
  border: "light-dark(#ecdccb, #3a332c)"
  border-strong: "light-dark(#e2b98f, #54493e)"
  foreground: "light-dark(#2b2b2b, #ede8e3)"
  muted: "light-dark(#5f6368, #b3aaa1)"
  primary: "light-dark(#b04d08, #ff9d4d)"
  primary-hover: "light-dark(#9c4507, #ffb371)"
  primary-foreground: "light-dark(#ffffff, #1a1008)"
  primary-soft: "light-dark(#fff1e4, #3a2412)"
  rail: "light-dark(#f7a14c, #3a2412)"
  rail-foreground: "light-dark(#1b1b1b, #ffffff)"
  rail-muted: "light-dark(#3a2410, #f3d2b4)"
  rail-hover: "light-dark(#f4913a, #4a2e17)"
  rail-active: "light-dark(#ffffff, #ff9d4d)"
  rail-active-foreground: "light-dark(#b04d08, #1a1008)"
  mod-cobalt: "light-dark(#1f4e8c, #8fb3e8)"
  mod-cobalt-soft: "light-dark(#e8eef7, #172338)"
  mod-teal: "light-dark(#0e7c86, #45b9c2)"
  mod-teal-soft: "light-dark(#e0f2f3, #0f2b33)"
  mod-green: "light-dark(#2e8b3e, #5cc96c)"
  mod-green-soft: "light-dark(#e6f4e8, #13291a)"
  mod-marigold: "light-dark(#f47920, #ff9d4d)"
  mod-marigold-soft: "light-dark(#fff1e4, #3a2412)"
  mod-marigold-text: "light-dark(#a34806, #ff9d4d)"
  mod-crimson: "light-dark(#d32f2f, #f17d71)"
  mod-crimson-soft: "light-dark(#fdeaea, #321714)"
  mod-ink-light: "light-dark(#ffffff, #141210)"
  mod-ink-dark: "#1f1500"
  next: "light-dark(#1a6fc4, #6fb2f5)"
  next-soft: "light-dark(#e6f0fb, #14263a)"
  next-foreground: "light-dark(#ffffff, #0b1624)"
  success: "light-dark(#2e7d32, #5cc96c)"
  success-soft: "light-dark(#e6f4e8, #13291a)"
  warning: "light-dark(#8f5400, #f0b45a)"
  warning-soft: "light-dark(#fdf1dc, #2d2313)"
  danger: "light-dark(#c62828, #f2877d)"
  danger-soft: "light-dark(#fdeaea, #331b19)"
  danger-foreground: "light-dark(#ffffff, #1f0a08)"
  info: "light-dark(#1565b8, #6fb2f5)"
  info-soft: "light-dark(#e6f0fb, #14263a)"
  focus: "light-dark(#1a6fc4, #6fb2f5)"
  series-1: "light-dark(#f47920, #ff9d4d)"
  series-2: "light-dark(#1a6fc4, #6fb2f5)"
  series-track: "light-dark(#fde3cc, #3a2a1c)"
  grid: "light-dark(#efe5da, #3a332c)"
typography:
  display:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.2
    fontFeature: "\"tnum\""
  headline:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  kpi:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.025em"
    fontFeature: "\"tnum\""
  title:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.43
  body:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
    fontFeature: "\"tnum\""
  label:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.33
  next-tag:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    letterSpacing: "0.025em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.title}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.surface-muted}"
  button-ghost:
    textColor: "{colors.foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.danger-foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-next:
    backgroundColor: "{colors.next}"
    textColor: "{colors.next-foreground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-sm:
    padding: "0 12px"
    height: "32px"
  badge:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
  next-tag:
    backgroundColor: "{colors.next}"
    textColor: "{colors.next-foreground}"
    typography: "{typography.next-tag}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  cluster-chip:
    backgroundColor: "{colors.mod-teal-soft}"
    textColor: "{colors.mod-teal}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "2px 6px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "16px 20px"
  stat-tile:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "20px 20px 16px"
  module-row:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "12px 16px"
  module-spine:
    backgroundColor: "{colors.mod-cobalt}"
    textColor: "{colors.mod-ink-light}"
    typography: "{typography.title}"
    width: "44px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "36px"
  nav-item:
    textColor: "{colors.rail-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-hover:
    backgroundColor: "{colors.rail-hover}"
    textColor: "{colors.rail-foreground}"
  nav-item-active:
    backgroundColor: "{colors.rail-active}"
    textColor: "{colors.rail-active-foreground}"
  table-header:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    padding: "8px 16px"
  meter:
    backgroundColor: "{colors.series-track}"
    rounded: "{rounded.full}"
    height: "8px"
  toast:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.foreground}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    padding: "12px 16px"
    width: "384px"
---

# Design System: Placement Readiness

## Overview

**Creative North Star: "The Module Booklets"**

Preparation is presented as a stack of numbered, colour-coded study modules, like the coaching booklets students already worked through. A committed UMS-orange rail with dark labels holds the navigation on a neutral grey ground with white, warm-outlined cards (warm charcoal in dark), echoing the university management system students already use. Primary actions use a deeper orange so white text stays at WCAG AA; UMS blue marks links, focus and the second data series. Each skill cluster owns one flat module hue, and that hue follows the skill everywhere it appears: the numbered spine of a gap or plan row, the swatch in a chip, the bar in a supply chart. One more hue, UMS blue, is held back for a single job: marking the one step the student should take next.

The system is dense and operational: small sentence-case type, bordered flat cards, full tables for staff, and numbers that line up because every figure is tabular. Depth comes from borders and tonal surfaces. Shadows appear only on layers that float (toasts, tooltips, menus, dialogs, the active theme segment, the auth card). Motion is short and functional: state transitions, a toast slide, meters filling on mount, a press scale on buttons. All of it collapses under reduced motion.

The build rejects the grey card dashboard with one indigo accent, gradients and glow, a neon dark-only look, and gamification. Light and dark are equal citizens: every colour token carries both values through `light-dark()`.

**Key Characteristics:**
- Committed orange shell rail (dark labels), full page height, white active pill.
- Five flat module hues mapped from skill clusters; blue reserved for "next".
- Numbered 44px module spines on gaps, plan items and steps.
- KPI tiles tied to a module by a 4px top band.
- One family (Geist), tabular numerals on body.
- Status is always icon plus label, never colour alone.
- Eligibility and readiness always rendered as separate blocks.

## Colors

A flat UMS palette: one committed orange, five cluster hues, a reserved blue, and status tones, each defined once with its light and dark value.

### Primary
- **Committed Cobalt** (`primary`, `rail`): the shell rail, primary buttons, active tabs, links, focus outline, and the info toast icon. In dark the rail deepens to a navy cobalt while `primary` lifts to a pale periwinkle so it stays readable on ink navy.
- **Cobalt Wash** (`primary-soft`): text selection, primary-tone badges.

### Secondary: module hues
Skill clusters map to hues in code (`lib/modules.ts`): programming, backend and frontend to **Cobalt**; databases and devops to **Lagoon Teal**; data to **Field Green**; testing to **Marigold**; cs-fundamentals to **Brick Crimson**. Clusters added later get a stable hue by hashing the cluster name over the same five. Each hue has a solid fill, a soft wash (`*-soft`) for chip backgrounds, and an ink for text on the solid: white (`mod-ink-light`) on all but Marigold, which takes the dark `mod-ink-dark`. Marigold text on a light ground uses the darker `mod-marigold-text` for contrast.

### Tertiary: reserved blue
- **Next-Step Blue** (`next`, `next-soft`, `next-foreground`): only the student's single next step: the border of the next ModuleRow, the NEXT / "Start here" tag, the `next` button variant, the "Make a plan from this drive" link, and the `next` badge tone.

### Status
- **Success / Warning / Danger / Info** (each with `-soft`): verification, eligibility, readiness, impact and drive-state badges, inline form messages, toasts. Warning text is a dark amber in light mode so it reads on its soft wash.

### Data
- **Series Cobalt** (`series-1`) on **Series Track** (`series-track`) for meters, columns and the readiness radar; **Grid** (`grid`) for chart rings and axes. `series-2` is teal. Where a bar belongs to a skill cluster, it takes the module hue instead of the series colour.

### Neutral
- **Practice-Sheet White / Ink Navy** (`background`): page ground.
- **Surface / Surface Muted / Surface Raised**: cards, table headers and the theme switch track, and floating layers.
- **Border / Border Strong**: 1px card and input strokes; strong on hover and for dashed empty states.
- **Foreground / Muted**: text and secondary text.

### Named Rules
**The Reserved Blue Rule.** The `next` blue marks the one next step and nothing else; each list shows at most one `next` item, and it is never used as a module fill.

**The Module Hue Rule.** A skill's colour comes from its cluster through `hueFor()`, never chosen per screen.

**The Flat Colour Rule.** Fills are solid tokens; no gradients and no glow anywhere.

## Typography

**Display Font:** Geist (with ui-sans-serif, system-ui, sans-serif)
**Body Font:** Geist (same family)
**Label/Mono Font:** Geist Mono is loaded as `--font-mono`; the UI is set in Geist.

**Character:** a single neutral grotesque carries everything; hierarchy comes from weight (400 / 500 / 600) and small size steps rather than a second family.

### Hierarchy
- **Display** (600, 1.875rem): the one large figure in a panel, such as overall readiness or a coding-activity rating.
- **Headline** (600, 1.25rem, tight tracking): page titles via the page header; the auth heading steps up to 1.5rem.
- **KPI** (600, 1.75rem, line-height 1, tight tracking): the value in a stat tile.
- **Title** (600, 0.875rem): card titles and module spine numbers.
- **Body** (400, 0.875rem): almost all UI text, tables and form controls.
- **Label** (500, 0.75rem): badges, chips, table headers, hints and timestamps.
- **Next tag** (600, 11px, uppercase, 0.025em): the NEXT tag only.

### Named Rules
**The Tabular Rule.** The body sets `font-variant-numeric: tabular-nums`, and tables, number inputs and `time` repeat it, so every column of figures lines up.

**The Sentence Case Rule.** Labels, titles and KPI captions are sentence case; uppercase belongs to the NEXT tag alone.

## Layout

The app shell is a 256px orange rail (from the `lg` breakpoint, 1024px) beside a sticky 56px header with the theme switch and notifications. Below `lg` the rail becomes a modal drawer (288px, max 85vw) that slides in from the left. Content sits in a centred column capped at 1400px, padded 16px / 24px / 32px as the viewport grows.

KPI tiles sit in a four-up grid at `xl` (1280px), two-up from `sm` (640px), and stack on mobile, with 16px gaps. The student dashboard pairs a left column of module spines (next steps with time budget, gaps, skill profile) with a right column of readiness radar, drives table and activity. Evaluation views put eligibility and compatibility side by side at `xl`, with readiness and gaps spanning the full width below. Cards pad 20px horizontally and 16px vertically; lists of module rows step by 8 to 10px. Wide tables scroll horizontally inside a focusable region.

Auth screens use a 416px cobalt story panel (three numbered steps) beside the form column (384px, or 576px for wide forms); the panel drops below `lg`.

### Named Rules
**The Two Blocks Rule.** Eligibility and readiness are always separate cards with separate badges, and never merge into one score or block.

## Elevation & Depth

The system is flat at rest. Cards, tiles, tables and module rows are separated by 1px borders and the tonal step from `background` to `surface`. Shadows are reserved for layers that float above the page.

### Shadow Vocabulary
- **Pop** (`--shadow-pop`: a 30px soft drop plus a 6px contact shadow, both darker in dark mode): toasts, chart tooltips, the skill-picker menu, the notification panel, and dialogs (onboarding, resume viewer).
- **Small** (Tailwind `shadow-sm`): the active segment of the theme switch and the auth form card.
- **Backdrop** (`rgb(8 14 31 / 0.55)`): modal dialogs and the mobile drawer.

### Named Rules
**The Floating-Only Shadow Rule.** Only floating layers cast a shadow; in-flow content is bordered and flat.

## Shapes

Corners are gently rounded and consistent: 6px on buttons, inputs and nav items; 8px on cards, tiles, module rows and toasts; 12px on the auth form card and dialogs; 4px on chips and the NEXT tag; full pills on badges, meters and the notification count. Borders are 1px throughout; the only thicker strokes are the 2px active tab underline and the 4px top band on KPI tiles. Module rows clip their spine inside the rounded corner (`overflow: hidden`), so the coloured number block reads as part of the card, not a stripe. Empty states use a dashed strong border.

### Named Rules
**The Top Band Rule.** A KPI tile shows its module hue as a 4px band across the top edge; coloured side borders thicker than 1px are not used. The module spine is a numbered fill cell, not a border.

## Components

### Buttons
Compact and quiet, with a tactile press.
- **Shape:** 6px radius; 36px tall (32px small), 16px (12px) horizontal padding, 0.875rem medium label, 8px icon gap.
- **Primary:** cobalt fill, white text; hover deepens to `primary-hover`.
- **Secondary:** surface fill with a 1px border; hover strengthens the border and moves to `surface-muted`.
- **Ghost:** text only; hover adds `surface-muted`.
- **Danger / Next:** solid danger or `next` blue fill; hover drops to 90% opacity. Next is used only for the single next action.
- **States:** 150ms ease-out transitions on colour, border, opacity and transform; `active` scales to 0.97; disabled is 50% opacity with no press scale. Focus uses the global 2px `focus` outline with a 2px offset.

### Badges and status
- **Style:** full pill, 0.75rem medium, soft tone wash with matching tone text (neutral, primary, success, warning, danger, info, next).
- **Status badges:** verification (Verified, Pending, Self-reported, Rejected), eligibility (Eligible / Not eligible / Not evaluated), readiness (Ready / Not yet ready) each pair a 14px lucide icon with the label.

**The Icon-Plus-Label Rule.** A status is never carried by colour alone; it is always a word, and verification, eligibility and readiness add an icon.

### Chips
- **Cluster chip:** 4px radius, the cluster's soft wash with its text hue, an 8px solid swatch, then the cluster name.

### Cards / Containers
- **Corner Style:** 8px.
- **Background:** `surface` on the `background` ground.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px `border`.
- **Internal Padding:** header 16px by 20px with a bottom divider and a 0.875rem semibold title plus muted description; body 16px by 20px.

### Stat tile (KPI)
Bordered 8px card with the 4px module-hue band on top, a muted sentence-case label with an optional icon in the hue, a 1.75rem tabular value, and an optional 0.75rem hint. Missing values render as an em dash, never an invented number.

### Module row (signature)
A bordered 8px row with a 44px numbered spine on the left: two-digit sequence (01, 02...) in 0.875rem semibold tabular figures on the cluster's solid hue, ink chosen per hue. The number is real order (gap rank or plan sequence). Done rows grey the spine to `surface-muted`; the next row swaps its border to the `next` blue and carries the NEXT tag. Hover strengthens the border in 150ms. The same spine appears in the auth story panel, where the first step uses white because a dark module hue would lose contrast on the rail.

### Inputs / Fields
- **Style:** 36px tall, 6px radius, 1px `border`, `surface` fill, 0.875rem text, label above in 0.875rem medium with 6px gap.
- **Focus:** border turns `primary`, plus the global focus outline.
- **Error / Disabled:** `aria-invalid` turns the border danger with a danger message below; disabled moves to `surface-muted` with muted text. Form-level errors are an inline danger-soft block that fades in.

### Navigation
- **Rail items:** 0.875rem, 8px by 12px, 6px radius, 16px lucide icon. Rest is `rail-muted`; hover fills `rail-hover`; the active item is a white pill with cobalt text and a heavier icon stroke.
- **Tabs:** underline tabs over a 1px divider; the active tab has a 2px cobalt underline and cobalt medium text.
- **Theme switch:** a segmented Light / System / Dark radio group (icon buttons, 28px by 32px) on a `surface-muted` track; the active segment lifts to `surface` with a small shadow. Arrow keys move the choice.
- **Mobile:** menu button opens the rail as a left drawer dialog.

**The Three-Way Theme Rule.** Theme is light, system or dark through `html[data-theme]`; with no attribute the OS preference applies, and an inline boot script restores a saved choice before first paint.

### Tables
Full-width 0.875rem tables; header cells are 0.75rem medium muted on a 60% `surface-muted` band; rows split by 1px borders with 16px by 10px cells.

### Meters and charts
- **Meter:** 8px pill track in `series-track`, `series-1` fill growing from the left on mount (220ms).
- **Bar list:** one measure per row, label and tabular value above the bar; cluster rows take the module hue for the swatch and bar.
- **Radar:** a single cobalt series over four grid rings, 12% fill and 2px stroke, with five axes (technical mastery, aptitude, communication, project depth, coding activity) when coding activity exists. Values are also listed as text beside it.
- **Time budget:** two meters, time used (muted) against work done (series), with "Behind schedule" in warning when time runs more than 10 points ahead of work.

### Toasts
Bottom-right stack (full width on mobile), at most four, 384px, `surface-raised` with a 1px border and the pop shadow, a tone icon, title and optional body, dismissable, auto-closing after 4.5s and paused on hover or focus. They slide up 8px and fade in over 200ms.

**The Inline Error Rule.** Mutations opt into a success toast through `meta.toast`; errors stay inline next to the control that failed.

### Coding activity
GitHub and LeetCode ratings are shown as supporting evidence with the evidence item's verification badge and the caption "Supporting evidence, not proof of expertise."

**The Evidence-Not-Proof Rule.** External coding activity is labelled with its verification status and never presented as verified expertise.

### Motion

**The Short Exponential Rule.** Transitions run 150 to 220ms on `cubic-bezier(0.22, 1, 0.36, 1)`, and a reduced-motion override cuts every animation and transition to near zero.

## Do's and Don'ts

### Do:
- **Do** take a skill's colour from its cluster through the module hue map, using solid for spines and bars, soft for chips.
- **Do** keep the `next` blue for the single next step: one such row, tag or button per list.
- **Do** tie KPI tiles to a module with the 4px top band.
- **Do** pair every status with a word, and with an icon for verification, eligibility and readiness.
- **Do** render eligibility and readiness as separate cards with separate badges.
- **Do** label external coding activity with its verification status as supporting evidence.
- **Do** show an em dash or an empty state where data does not exist.
- **Do** keep transitions between 150 and 220ms on the exponential ease-out, and honour reduced motion.
- **Do** define every new colour with `light-dark()` so both themes stay in step.

### Don't:
- **Don't** use gradients or glow.
- **Don't** use coloured side borders thicker than 1px as an accent.
- **Don't** use the `next` token as a module hue or general emphasis (the second chart series uses its own `series-2` token).
- **Don't** add a second type family or proportional figures for numbers.
- **Don't** put shadows on in-flow cards, tiles or rows.
- **Don't** show errors as toasts.
- **Don't** merge eligibility and readiness into one score or block.
