# ADR 0005: Small in-house UI primitives before adopting shadcn/ui

- Status: accepted (2026-10-20)

## Context
CES requires a component library and design tokens before feature work. The plan named shadcn/ui. Current screens need only buttons, cards, badges, fields, tabs and tables.

## Decision
Define semantic design tokens (light and dark) in `app/globals.css` and a minimal set of accessible primitives in `components/ui/`. Adopt Radix/shadcn components when a screen first needs dialogs, menus, popovers or comboboxes, rather than adding those dependencies up front.

## Consequences
- Fewer dependencies now, and the styling rules are consistent in one place.
- Complex interactive widgets must not be hand-rolled. Pull in Radix/shadcn when they are needed.
