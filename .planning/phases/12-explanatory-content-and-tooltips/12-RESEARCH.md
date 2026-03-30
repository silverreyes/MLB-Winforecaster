# Phase 12: Explanatory Content and Tooltips - Research

**Researched:** 2026-03-30
**Domain:** React 19 collapsible section + CSS tooltip UI (pure frontend, no backend)
**Confidence:** HIGH

## Summary

Phase 12 adds two distinct UI features to the existing React 19 + Vite 8 + CSS Modules dashboard: (1) a collapsible "About the Models" explanatory section placed below the AccuracyStrip and above the game card grid, and (2) inline (?) tooltip icons on the EdgeBadge Buy Yes / Buy No labels within each game card's Kalshi section. Both features are purely presentational -- no new API calls, no data fetching, no external libraries.

The existing codebase uses a consistent pattern: functional React components with CSS Modules (`.module.css`), CSS custom properties from `index.css` (dark amber palette: `--color-bg`, `--color-surface`, `--color-border`, `--color-accent`, etc.), DM Sans for UI text and DM Mono for data values. There are zero third-party UI libraries -- all layout is hand-written CSS. The collapsible section should use the native HTML `<details>` / `<summary>` element pair, which provides correct keyboard accessibility and expand/collapse semantics with zero JavaScript. The tooltips should use pure CSS hover/focus positioning with `title` attribute as fallback, avoiding any tooltip library.

**Primary recommendation:** Build two new components (`AboutModels.tsx` + `Tooltip.tsx`) using the existing CSS Modules + custom properties pattern. Use native `<details>`/`<summary>` for collapse/expand. Use a pure-CSS tooltip component with `position: absolute` relative to a `position: relative` wrapper. No new npm dependencies.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXPLAIN-01 | Dashboard includes a collapsible "About the Models" section | Native `<details>`/`<summary>` HTML element provides collapse/expand with default-collapsed, keyboard accessible, zero JS |
| EXPLAIN-02 | Section explains LR, RF, XGBoost in one plain-English sentence each | Static content in AboutModels component; copy provided in Code Examples |
| EXPLAIN-03 | Section explains what the probability number means | Static content paragraph; copy provided in Code Examples |
| EXPLAIN-04 | Section explains calibration meaning | Static content paragraph; copy provided in Code Examples |
| EXPLAIN-05 | Section distinguishes PRE-LINEUP from POST-LINEUP | Static content paragraph; copy provided in Code Examples |
| EXPLAIN-06 | Section explains Kalshi as regulated prediction market | Static content paragraph; neutral informational tone; copy provided in Code Examples |
| EXPLAIN-07 | Kalshi explanation includes 7% fee disclosure; no trading recommendations | Fee disclosure in copy; verified no action-oriented language; copy provided in Code Examples |
| TLTP-01 | Buy Yes label has inline (?) tooltip explaining contract mechanics | Tooltip component on EdgeBadge; appears on hover/focus; copy: "Pays $1 if [home team] wins. You pay the displayed price." |
| TLTP-02 | Buy No label has inline (?) tooltip explaining contract mechanics | Tooltip component on EdgeBadge; appears on hover/focus; copy: "Pays $1 if [home team] loses. You pay 1 minus the Yes price." |
</phase_requirements>

## Standard Stack

### Core (already installed -- no changes)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.4 | UI rendering | Already in use; collapsible + tooltip are native HTML/CSS |
| react-dom | 19.2.4 | DOM rendering | Already in use |
| vite | 8.0.3 | Build tool | Already in use |
| typescript | 5.9.3 | Type checking | Already in use; strict mode enabled |

### Supporting
No new supporting libraries needed. The collapsible section and tooltips are implementable with native HTML elements and CSS only.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `<details>` | `useState` + div | `<details>` is accessible by default, has no JS, and animates with CSS `[open]` selector; `useState` adds unnecessary state management |
| CSS-only tooltip | @floating-ui/react or react-tooltip | Overkill for a simple inline hint; adds a dependency; the tooltip content is short and static |
| `title` attribute | Custom tooltip | `title` has inconsistent styling across browsers and no control over appearance; custom CSS tooltip is better UX |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
  components/
    AboutModels.tsx           # NEW - collapsible explanatory section
    AboutModels.module.css    # NEW - styles for about section
    Tooltip.tsx               # NEW - reusable CSS tooltip wrapper
    Tooltip.module.css        # NEW - tooltip positioning + arrow
    EdgeBadge.tsx             # MODIFIED - add (?) tooltip icons
    EdgeBadge.module.css      # MODIFIED - tooltip trigger styling
    KalshiSection.tsx         # MODIFIED - pass home_team to EdgeBadge for tooltip copy
  App.tsx                     # MODIFIED - add AboutModels between AccuracyStrip and main
```

### Pattern 1: Native `<details>` / `<summary>` for Collapsible Content

**What:** Use the HTML `<details>` element which provides built-in expand/collapse behavior, keyboard accessibility (Enter/Space to toggle), and screen reader support -- all with zero JavaScript.

**When to use:** Any collapsible section that defaults to collapsed and doesn't need controlled open/close from external state.

**Example:**
```typescript
// Source: MDN Web Docs - <details> element
// https://developer.mozilla.org/en-US/docs/Web/HTML/Element/details
export function AboutModels() {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>
        <span className={styles.summaryText}>About the Models</span>
        <span className={styles.chevron} aria-hidden="true" />
      </summary>
      <div className={styles.content}>
        {/* Explanatory content here */}
      </div>
    </details>
  );
}
```

**Key CSS for `<details>`:**
```css
/* <details> defaults to closed -- no defaultOpen needed */
.details[open] .chevron {
  transform: rotate(90deg);
}

.summary {
  cursor: pointer;
  list-style: none; /* Remove default triangle */
}

.summary::-webkit-details-marker {
  display: none; /* Chrome/Safari default marker removal */
}
```

### Pattern 2: Pure CSS Tooltip

**What:** A reusable tooltip component using CSS `position: absolute` inside a `position: relative` wrapper, shown on `:hover` and `:focus-visible`. No JavaScript state management needed.

**When to use:** Short, static tooltip content triggered by an icon that doesn't need programmatic control.

**Example:**
```typescript
interface TooltipProps {
  text: string;
  children: React.ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <span className={styles.wrapper}>
      {children}
      <span className={styles.tip} role="tooltip">{text}</span>
    </span>
  );
}
```

**Key CSS for tooltip:**
```css
.wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: 12px;
  padding: var(--space-xs) var(--space-sm);
  border-radius: 4px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s ease;
  z-index: 10;
}

.wrapper:hover .tip,
.wrapper:focus-visible .tip {
  opacity: 1;
}
```

### Pattern 3: Existing Component Conventions

The codebase follows these conventions consistently -- new components MUST match:

- **CSS Modules**: Every component has a paired `.module.css` file
- **CSS custom properties**: All colors from `:root` vars (`--color-*`), all spacing from `--space-*`
- **Font families**: `--font-ui` (DM Sans) for labels/text, `--font-data` (DM Mono) for numbers
- **Component exports**: Named exports (`export function ComponentName`), not default exports
- **No inline styles**: All styling via CSS Modules `styles.className`
- **Mobile breakpoint**: `@media (max-width: 768px)` used in Header and GameCardGrid

### Anti-Patterns to Avoid
- **Don't use `useState` for the collapsible section**: `<details>` handles this natively with zero JS. Adding React state for open/close is unnecessary complexity.
- **Don't install a tooltip library**: The tooltips show 1-2 lines of static text on 2 elements. A library like `@floating-ui/react` or `react-tooltip` would add bundle weight for no benefit.
- **Don't use `title` attribute for tooltips**: Browser-native `title` tooltips have inconsistent styling, delayed appearance, and cannot be styled to match the dark amber design system.
- **Don't use absolute pixel values**: All spacing and colors MUST use the existing CSS custom properties.
- **Don't persist collapsible state in localStorage**: Explicitly listed as out of scope in REQUIREMENTS.md.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collapsible section | Custom `useState` + height animation + aria-expanded | Native `<details>` / `<summary>` | Built-in accessibility, keyboard support, no JS; CSS handles chevron rotation via `[open]` selector |
| Tooltip positioning | Custom JS positioning with `getBoundingClientRect` | CSS `position: absolute` with `bottom: calc(100% + offset)` | Tooltip content is short (no overflow risk on reasonable viewports); pure CSS is simpler and faster |

**Key insight:** Both features in this phase are solved problems at the HTML/CSS level. Adding JavaScript or npm dependencies would be over-engineering for static informational content.

## Common Pitfalls

### Pitfall 1: `<details>` Default Triangle Marker
**What goes wrong:** The browser renders a default disclosure triangle on `<summary>` that doesn't match the dark amber design.
**Why it happens:** Browsers apply `list-style-type: disclosure-*` and `::-webkit-details-marker` by default.
**How to avoid:** Apply both `list-style: none` on `<summary>` and `display: none` on `::-webkit-details-marker` pseudo-element. Use a custom CSS chevron via `border` or a Unicode character.
**Warning signs:** A small triangle appears to the left of "About the Models" text.

### Pitfall 2: Tooltip Overflow on Small Screens
**What goes wrong:** A tooltip positioned above the (?) icon can overflow off the left/right edge of the viewport on mobile.
**Why it happens:** `left: 50%; transform: translateX(-50%)` centers the tooltip, but the EdgeBadge may be near a viewport edge.
**How to avoid:** For these specific tooltips, use `white-space: normal` with a `max-width: 220px` and allow text wrapping. Position the tooltip to the left (right-aligned) if the badge is near the right edge. Given that the KalshiSection is inside a card grid with padding, overflow is unlikely but should be tested.
**Warning signs:** Tooltip text is cut off or extends past the viewport boundary on 375px-wide screens.

### Pitfall 3: Tooltip Not Accessible on Touch Devices
**What goes wrong:** CSS `:hover` tooltips don't work on touch devices (phones/tablets) where there is no hover state.
**Why it happens:** Touch devices don't fire mouse hover events the same way.
**How to avoid:** Add `:focus-visible` alongside `:hover` so keyboard and tap-to-focus users can see the tooltip. Make the (?) icon a `<button>` element (or use `tabIndex={0}`) so it receives focus. Consider also toggling on touch via a minimal `onClick` handler that toggles visibility.
**Warning signs:** Mobile users tap the (?) icon and nothing happens.

### Pitfall 4: Forgetting the Non-Recommendation Constraint (EXPLAIN-07)
**What goes wrong:** Copy for the Kalshi section uses action-oriented language like "you can buy contracts" or "consider purchasing" that could be construed as trading advice.
**Why it happens:** Natural tendency to make explanatory content actionable.
**How to avoid:** Use strictly neutral, descriptive language. Focus on "what it is" not "what you should do." The copy should describe mechanics (prices, fees, payouts) without suggesting action. Review against EXPLAIN-07 explicitly.
**Warning signs:** Any sentence containing "you should," "consider buying," "take advantage," "opportunity," or similar action verbs directed at the reader.

### Pitfall 5: EdgeBadge Tooltip Needs Home Team Context
**What goes wrong:** The tooltip text says "pays $1 if home team wins" but doesn't have access to the actual home team name.
**Why it happens:** `EdgeBadge` currently only receives `signal` and `magnitude` -- no team context.
**How to avoid:** The tooltip text can use generic "home team" / "home team loses" language (per requirements spec), OR `KalshiSection` can pass `homeTeam` down. The requirements use generic language, so generic is fine.
**Warning signs:** N/A -- requirements spec uses generic "home team" phrasing.

## Code Examples

Verified patterns from existing codebase and official sources:

### AboutModels Component Structure
```typescript
// Follows existing component pattern (named export, CSS module import)
import styles from './AboutModels.module.css';

export function AboutModels() {
  return (
    <div className={styles.container}>
      <details className={styles.details}>
        <summary className={styles.summary}>
          <span className={styles.summaryText}>About the Models</span>
          <span className={styles.chevron} aria-hidden="true">{'\u25B6'}</span>
        </summary>
        <div className={styles.content}>
          <section className={styles.section}>
            <h3 className={styles.heading}>Model Types</h3>
            <ul className={styles.list}>
              <li><strong>Logistic Regression (LR)</strong> — A linear model that weights each
              stat (win rate, ERA, etc.) to estimate win probability. Simple and interpretable.</li>
              <li><strong>Random Forest (RF)</strong> — Builds hundreds of decision trees on random
              subsets of the data, then averages their predictions. Handles complex stat interactions.</li>
              <li><strong>XGBoost (XGB)</strong> — Builds decision trees sequentially, with each tree
              correcting the previous ones' errors. Often the most accurate on structured data.</li>
            </ul>
            <p className={styles.paragraph}>The <strong>ensemble</strong> probability shown on each
            card averages all three models for a more stable estimate.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Reading the Probabilities</h3>
            <p className={styles.paragraph}>A probability of <strong>68%</strong> means the home
            team wins in roughly 68 out of 100 similar matchups.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Calibration</h3>
            <p className={styles.paragraph}>These models are <em>calibrated</em>: when they say
            70%, the home team has historically won about 70% of the time. The Brier scores above
            measure calibration accuracy (lower is better).</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>PRE-LINEUP vs. POST-LINEUP</h3>
            <p className={styles.paragraph}><strong>PRE-LINEUP</strong> predictions use only
            team-level stats (win rate, run differential, etc.) and carry more uncertainty.
            <strong>POST-LINEUP</strong> predictions incorporate confirmed starting pitcher data
            and are the primary signal.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Kalshi Market Prices</h3>
            <p className={styles.paragraph}>Kalshi is a regulated prediction market where contracts
            pay $1 if an outcome occurs. A price of 62c implies the market estimates a 62% chance
            the home team wins. The edge signal compares model probability against market price.</p>
            <p className={styles.disclaimer}>Kalshi charges a 7% fee on net profits. Displayed
            prices do not account for this fee. Nothing on this dashboard is trading advice or a
            recommendation to buy or sell contracts.</p>
          </section>
        </div>
      </details>
    </div>
  );
}
```

### AboutModels CSS Module
```css
/* Follows existing pattern: CSS Modules + custom properties */
.container {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.details {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--space-lg);
}

.summary {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) 0;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.summary::-webkit-details-marker {
  display: none;
}

.summaryText {
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
}

.chevron {
  font-size: 8px;
  color: var(--color-text-secondary);
  transition: transform 0.2s ease;
}

.details[open] .chevron {
  transform: rotate(90deg);
}

.content {
  padding: 0 0 var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.section {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.heading {
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent);
  margin: 0;
}

.list {
  margin: 0;
  padding-left: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.list li {
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.paragraph {
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
  margin: 0;
}

.disclaimer {
  font-family: var(--font-ui);
  font-size: 12px;
  color: var(--color-stale);
  line-height: 1.5;
  margin: 0;
  font-style: italic;
}
```

### Tooltip Component
```typescript
import styles from './Tooltip.module.css';

interface TooltipProps {
  text: string;
  children?: React.ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <span className={styles.wrapper} tabIndex={0} role="button" aria-label={text}>
      {children ?? <span className={styles.icon}>?</span>}
      <span className={styles.tip} role="tooltip">{text}</span>
    </span>
  );
}
```

### Tooltip CSS Module
```css
.wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: help;
}

.wrapper:focus {
  outline: none;
}

.wrapper:focus-visible {
  outline: 1px solid var(--color-accent);
  outline-offset: 2px;
  border-radius: 50%;
}

.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  line-height: 1;
  flex-shrink: 0;
}

.tip {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-family: var(--font-ui);
  font-size: 12px;
  line-height: 1.4;
  padding: var(--space-xs) var(--space-sm);
  border-radius: 4px;
  max-width: 220px;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.15s ease;
  z-index: 10;
}

.wrapper:hover .tip,
.wrapper:focus-visible .tip {
  opacity: 1;
  visibility: visible;
}

@media (max-width: 768px) {
  .tip {
    left: auto;
    right: 0;
    transform: none;
  }
}
```

### EdgeBadge Modification (adding tooltip)
```typescript
// EdgeBadge.tsx -- add tooltip icons next to BUY YES / BUY NO labels
import { Tooltip } from './Tooltip';
import styles from './EdgeBadge.module.css';

interface EdgeBadgeProps {
  signal: 'BUY_YES' | 'BUY_NO';
  magnitude: number;
}

const TOOLTIP_YES = 'Pays $1 if the home team wins. You pay the displayed price.';
const TOOLTIP_NO = 'Pays $1 if the home team loses. You pay 1 minus the Yes price.';

export function EdgeBadge({ signal, magnitude }: EdgeBadgeProps) {
  const isBuyYes = signal === 'BUY_YES';
  const text = isBuyYes
    ? `BUY YES +${magnitude.toFixed(1)}pts`
    : `BUY NO -${Math.abs(magnitude).toFixed(1)}pts`;
  const tooltipText = isBuyYes ? TOOLTIP_YES : TOOLTIP_NO;

  return (
    <span className={`${styles.badge} ${isBuyYes ? styles.buyYes : styles.buyNo}`}>
      {text}
      <Tooltip text={tooltipText} />
    </span>
  );
}
```

### App.tsx Integration Point
```typescript
// Add AboutModels between AccuracyStrip and NewPredictionsBanner
import { AboutModels } from './components/AboutModels';

// In the JSX:
<Header ... />
<AccuracyStrip />
<AboutModels />         {/* NEW -- EXPLAIN-01 through EXPLAIN-07 */}
<NewPredictionsBanner ... />
<main>...</main>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom JS accordion with `useState` | Native `<details>`/`<summary>` | Always available, but adoption grew with CSS customization support | Zero JS needed; built-in keyboard/screen reader support; `[open]` CSS selector for styling |
| Tooltip libraries (tippy.js, react-tooltip) | CSS-only tooltips for simple cases | Ongoing trend as CSS capabilities improve | No bundle impact; sufficient for static 1-2 line tooltip text |
| `title` attribute | Custom styled tooltips | Long-standing best practice | `title` is unstyled, delayed, and inconsistent across browsers |

**Deprecated/outdated:**
- None relevant -- native HTML elements are the most current approach for this use case.

## Open Questions

1. **Tooltip on touch devices**
   - What we know: CSS `:hover` doesn't activate on touch. `:focus-visible` works if the element is focusable.
   - What's unclear: Whether `tabIndex={0}` + `:focus-visible` provides a good enough UX on iOS Safari (some versions have quirks with focus on non-interactive elements).
   - Recommendation: Make the (?) a focusable `<span>` with `tabIndex={0}`. This handles keyboard and most touch scenarios. If touch proves problematic in testing, add a minimal `onClick` toggle as a follow-up.

2. **Chevron animation on `<details>` open/close**
   - What we know: The `[open]` attribute on `<details>` is set/removed synchronously when toggling. CSS `transition` on the chevron `transform` works.
   - What's unclear: Whether content height animation is desired (smooth expand/collapse of the content area).
   - Recommendation: Do NOT animate content height -- it adds significant CSS/JS complexity (`@starting-style`, `calc-size()` or JS-based height measurement). A simple instant show/hide with chevron rotation is clean and matches the existing minimal aesthetic.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None configured for frontend (no vitest/jest setup) |
| Config file | none -- see Wave 0 |
| Quick run command | `cd frontend && npx tsc --noEmit` (type-check only) |
| Full suite command | `cd frontend && npm run build` (type-check + Vite build) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPLAIN-01 | Collapsible section renders with `<details>` | manual | Visual inspection: section collapsed by default, click toggles | N/A |
| EXPLAIN-02 | Model type descriptions present | manual | Visual inspection: LR, RF, XGB sentences visible when expanded | N/A |
| EXPLAIN-03 | Probability interpretation text | manual | Visual inspection: "68 out of 100" text present | N/A |
| EXPLAIN-04 | Calibration explanation text | manual | Visual inspection: calibration paragraph present | N/A |
| EXPLAIN-05 | PRE vs POST distinction text | manual | Visual inspection: both terms explained | N/A |
| EXPLAIN-06 | Kalshi market explanation | manual | Visual inspection: market mechanics described | N/A |
| EXPLAIN-07 | 7% fee disclosure, no trading recommendations | manual | Text review: fee mentioned, no action verbs | N/A |
| TLTP-01 | Buy Yes tooltip on hover/focus | manual | Hover (?) next to BUY YES badge; tooltip appears | N/A |
| TLTP-02 | Buy No tooltip on hover/focus | manual | Hover (?) next to BUY NO badge; tooltip appears | N/A |
| ALL | TypeScript compiles cleanly | type-check | `cd frontend && npx tsc --noEmit` | N/A |
| ALL | Vite build succeeds | build | `cd frontend && npm run build` | N/A |

### Sampling Rate
- **Per task commit:** `cd frontend && npx tsc --noEmit` (type-check in ~3s)
- **Per wave merge:** `cd frontend && npm run build` (full build in ~10s)
- **Phase gate:** Build success + visual inspection of collapsed/expanded states and tooltip hover

### Wave 0 Gaps
None -- no test framework is needed for this phase. All requirements are static UI content verifiable through type-checking (compile) and visual inspection. The existing `npm run build` command (tsc + vite build) catches type errors and module resolution issues. A frontend test framework (vitest) would be valuable for future phases but is not required for static content components.

## Sources

### Primary (HIGH confidence)
- **Existing codebase** - All 14 component files in `frontend/src/components/` read and analyzed for patterns, conventions, CSS variable usage, and component structure
- **MDN Web Docs** - `<details>`/`<summary>` element specification, CSS `:hover`/`:focus-visible` pseudo-classes
- **package.json** - Verified installed versions: React 19.2.4, Vite 8.0.3, TypeScript 5.9.3

### Secondary (MEDIUM confidence)
- None needed -- this phase uses only native HTML elements and CSS patterns

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new packages; existing stack fully sufficient
- Architecture: HIGH - Two simple presentational components following established codebase patterns
- Pitfalls: HIGH - Standard HTML/CSS patterns; pitfalls are well-documented (details marker, tooltip positioning, touch accessibility)

**Research date:** 2026-03-30
**Valid until:** 2026-05-30 (60 days -- stable native HTML/CSS patterns, no rapidly moving dependencies)
