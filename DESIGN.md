# Design System: Leverage Lab

<!-- impeccable:design-schema 1 -->

## Archetype

**Modern FinTech / Clean Studio (Linear & Stripe Inspired)**
A disciplined, high-craft dark interface designed for analytical precision. Zero gradient text, zero glowing halo drop-shadows, zero purple/cyan AI tells, and zero bounce animations. The interface recedes to let quantitative financial data, drawdown curves, and strategy metrics lead.

---

## Color Palette & Tokens

### Backgrounds & Surfaces
- `--bg-canvas`: `#09090b` (Deep neutral zinc page background)
- `--bg-surface`: `#121215` (Primary panel & card surface)
- `--bg-surface-elevated`: `#18181b` (Hover states, elevated dropdowns, modal layers)
- `--bg-subtle`: `#1f1f23` (Table header rows, active segment backgrounds)

### Borders & Dividers
- `--border-subtle`: `rgba(255, 255, 255, 0.07)` (Standard structural hairline borders)
- `--border-hover`: `rgba(255, 255, 255, 0.14)` (Interactive hover borders)
- `--border-focus`: `#3b82f6` (Keyboard focus ring / active state outline)

### Typography Colors
- `--text-primary`: `#fafafa` (Solid white headings, primary values)
- `--text-secondary`: `#a1a1aa` (Subtitles, table headers, descriptions)
- `--text-muted`: `#71717a` (Footnotes, passive labels, units)

### Interactive & Status Accents
- `--accent-primary`: `#3b82f6` (Electric Blue for active toggles, universe switch, primary buttons)
- `--accent-primary-dim`: `rgba(59, 130, 246, 0.12)`
- `--green`: `#10b981` (Emerald for positive returns, Sharpe ratio highlights)
- `--green-dim`: `rgba(16, 185, 129, 0.12)`
- `--red`: `#f43f5e` (Rose for drawdowns and negative returns)
- `--red-dim`: `rgba(244, 63, 94, 0.12)`
- `--amber`: `#f59e0b` (Warnings, cash allocations, regime transitions)
- `--amber-dim`: `rgba(245, 158, 11, 0.12)`

---

## Typography

### Font Families
- **Interface & Headings**: `'Figtree', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
  - Clean geometric structure with subtle craft ink-traps.
- **Financial Metrics, Tables & Data**: `'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace`
  - Strict tabular numbers (`font-variant-numeric: tabular-nums`) for currency amounts, percentages, Sharpe ratios, dates, and column alignment.

### Typographic Scale
- Display / Hero Title: `2rem` (32px), weight 600, tracking `-0.025em`, solid color (no gradients).
- Section Title: `1.25rem` (20px), weight 600, tracking `-0.015em`.
- Card / Panel Header: `1rem` (16px), weight 600.
- Body Copy: `0.875rem` (14px), line-height 1.5, weight 400.
- Labels & Subtitles: `0.75rem` (12px), weight 500, uppercase letter-spacing `0.05em`.
- Metrics / Stat Values: `1.25rem`–`1.5rem`, weight 600, JetBrains Mono tabular.

---

## Elevation & Radii

- **Shadows**:
  - Panel Elevation: `0 1px 3px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.06)`
  - Elevated Dropdown/Pop: `0 8px 24px -4px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08)`
  - *Strict Rule: No zero-offset colored blur glows (e.g. `0 0 30px rgba(99, 102, 241, 0.3)`).*
- **Border Radii**:
  - Shell / Container: `12px`
  - Cards & Panels: `8px`
  - Buttons, Badges, Tabs: `6px`
  - Universe Toggle Pill: `8px` (segmented control)

---

## Transitions & Motion

- Duration: `150ms` – `200ms`
- Timing Function: `cubic-bezier(0.16, 1, 0.3, 1)` (smooth deceleration)
- *Strict Rule: Zero bounce or elastic spring curves.*
