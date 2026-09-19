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

---

## Responsive & Mobile Architecture

### Breakpoint Conventions
- **Desktop Wide**: `> 1100px` (Full multi-column dashboard grid, persistent full filters, 550px charts).
- **Tablet / Small Laptop**: `<= 900px` (2-column stats, stacked secondary HUDs, single-column layouts).
- **Mobile Viewports**: `<= 768px` (Single column, horizontal swipeable navigation, sticky table column, bottom-sheet modals).
- **Compact Mobile**: `<= 480px` (1-column stat cards, full-width buttons, 290px compact charts, condensed padding).

### Mobile Interaction Patterns
1. **Touch Target Floor**:
   - All interactive controls (buttons, tabs, segment controls, dropdown triggers, close buttons) adhere to a minimum touch floor of `42px–44px` with adequate tap padding.
2. **Horizontal Pill Tabs**:
   - Navigation tabs on mobile convert to horizontally swipeable scrollbars with `-webkit-overflow-scrolling: touch` and hidden scrollbars (`scrollbar-width: none`).
3. **Sticky Column Data Tables**:
   - Data tables retain the primary descriptor column (Strategy / Date) locked to the left via `position: sticky; left: 0;` with an elevated background (`#121215` / `#09090b`), hairline right border, and subtle drop shadow while performance metrics scroll smoothly horizontally.
4. **Collapsible Filter Accordion**:
   - Date range and universe selectors collapse into an interactive summary row on mobile, expanding smoothly on user demand to preserve vertical viewport for analytics.
5. **Adaptive Chart Heights & Resize Observers**:
   - Desktop: `550px`
   - Mobile (`<= 768px`): `320px`
   - Compact (`<= 480px`): `290px`
   - Charts dynamically re-render on orientation and dimension changes via `Plotly.Plots.resize`.
6. **Bottom Sheet Modals**:
   - On screens `<= 768px`, dialog modals transition from centered desktop cards into slide-up bottom sheets (`max-height: 85vh`, rounded top corners `16px`, sticky header with a `44px` touch close target, safe-area inset bottom padding).

