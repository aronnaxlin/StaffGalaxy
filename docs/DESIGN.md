# Staff Galaxy Design System

Last updated: 2026-05-27

## Reference Sources

- `https://bangumi.tv/`
- `https://bgm.tv/`
- `https://chii.in/`
- `https://bgm.tv/person/1040`

Observed traits to borrow, not copy: dark top shell, rounded category pills, compact metadata, soft pink/cyan accents, dense link lists, small poster/card grids, and profile pages that pair a visual identity area with readable long-form facts.

## Product Tone

Staff Galaxy should feel like a night-sky research instrument connected to Bangumi's database culture:

- Graph canvas: spatial, dark, quiet, and fast.
- Search and panels: compact, library-like, rounded, and evidence-first.
- Evidence cards: factual, scannable, link-rich, and never decorative for its own sake.
- Interactions: subtle enough for large data exploration; highlights should clarify focus and path, not entertain.

## Color Tokens

Use Tailwind classes where possible. When hard-coded colors are needed, keep them aligned with these tokens.

| Token | Value | Use |
|---|---:|---|
| `galaxy.bg` | `#0a0a0f` | Main graph background |
| `galaxy.bgAlt` | `#080810` | Constellation/path background |
| `panel.bg` | `rgba(2, 6, 23, 0.92)` | Side panels, overlays |
| `panel.bgSoft` | `rgba(15, 23, 42, 0.72)` | Nested evidence blocks |
| `panel.border` | `rgba(51, 65, 85, 0.60)` | Panel borders |
| `text.primary` | `#f1f5f9` | Names and main labels |
| `text.secondary` | `#cbd5e1` | Body facts |
| `text.muted` | `#64748b` | Timestamps, IDs, counts |
| `accent.cyan` | `#22d3ee` | Graph focus, links, strong action |
| `accent.pink` | `#fb7185` | Bangumi-flavored highlight, warnings used gently |
| `accent.gold` | `#fbbf24` | Path endpoints and selected constellation nodes |
| `accent.violet` | `#c084fc` | Secondary path color, keyboard-selected search row |
| `state.error` | `#f87171` | Load/query errors |

Avoid one-hue purple gradients, beige/tan defaults, decorative blob backgrounds, and large atmospheric illustrations. The graph is the visual hero.

## Typography

- Font stack: `system-ui, "Segoe UI", sans-serif`.
- Base size: `14px`.
- Dense metadata: `10px` to `12px`, uppercase only for short labels.
- Panel names: `16px`, semibold.
- Graph hover labels: `14px`, medium, no wrapping.
- Line height: 1.35 for metadata, 1.6 for prose/evidence summaries.
- Letter spacing: only use positive tracking for tiny uppercase labels; never negative.

## Shape, Spacing, Shadow

- Controls and cards: `8px` radius by default.
- Large side panels: `12px` radius, matching current `rounded-xl`.
- Pills and tiny toggles: `999px` or tightly rounded segmented controls.
- Panel padding: `16px`.
- Dense list rows: `6px 8px`.
- Evidence card gaps: `6px` to `8px`.
- Shadow: one soft overlay shadow for side panels; avoid stacking cards inside cards.

## Layout

### Desktop

- Graph canvas is full viewport and unframed.
- Global search sits in the top-left control rail beside the product mark.
- Side panels float above the graph on the right with max height bounded by viewport.
- Constellation view uses a fixed left sidebar and full remaining SVG canvas.
- Evidence lists scroll inside the panel, not the whole page.

### Mobile/Small Width

Mobile is not full-scope yet, but new work must not create impossible states:

- Side panels should be able to become full-width bottom sheets later.
- Text must wrap or truncate before it overlaps.
- Controls should keep at least `32px` touch height when adapted.

## Components

### Search

- Search is a single input: name, CJK variant, or Bangumi ID.
- Result rows show name, degree, ID, and a small Bangumi external link.
- Person-name display uses a compact `原名` / `简中` / `繁中` segmented control. `简中` and `繁中` only use Archive-provided `简体中文名` and `繁体中文名` / `繁體中文名`, falling back to the original name when missing.
- Keyboard-selected rows use a restrained violet/cyan tint.
- Locked selected people render as pills with ID and external link.
- Loading spinner is small and inline at the right edge.

### Graph Canvas

- Nodes are people only.
- Node color communicates graph state first: default, hover, selected, path, center, future community.
- Role tier must not permanently color a person; it may appear as filter or highlight state.
- Labels appear on hover, selected, search hit, path, or high-zoom local view.
- Edge opacity and width reflect visible collaboration strength; hidden edges still exist in complete queries.

### Person Panel

Required content:

- Display name and Bangumi ID/link.
- Visible collaborator count and weighted degree when available.
- Role layer tag, clearly marked as render/evidence layer.
- Direct collaborators sorted by shared work count.
- Expandable collaboration evidence cards with roles, years, score, subject links, and title preference.
- Compact add-to-compare action on each collaborator opens `/compare?from={current}&to={collaborator}`.

Pending content:

- Alias list from richer source fields.
- Representative/recent works summary.
- Data snapshot indicator.

### Collaboration Evidence

- Always show whether evidence came from complete query or visible graph context.
- Shared works should link to `/subject/{id}` through the configured Bangumi base URL.
- Work title preference supports:
  - `original`: original/Japanese title first.
  - `cn`: Chinese title first when present, falling back to original.
- Roles must remain per-work facts, not permanent person categories.

### Constellation / Path

- Left sidebar controls pair selection, direct comparison, and path legend.
- Direct degree-1 comparison shows shared works and roles before the path legend.
- Degree-2+ results explicitly state that no direct evidence was found.
- Path endpoints use gold; alternate shortest paths use cyan/violet/pink/green.
- Each path step label shows shared work count.
- Person labels in path legends link to `/person/{id}`.

### Loading, Empty, Error

- Loading: short Chinese status text plus small spinner only where needed.
- Empty search: no dropdown, no explanatory prose.
- No direct evidence: factual and neutral, not an error.
- No path: error-colored panel with backend reason.
- Backend unavailable: show concise failure near the control that triggered it.

## Link Policy

- Base URL comes from `VITE_BANGUMI_BASE_URL`, defaulting to `https://bgm.tv`.
- Person link format: `/person/{id}`.
- Subject link format: `/subject/{id}`.
- External links open in a new tab with `rel="noopener noreferrer"`.
- Use small arrow/link affordances to avoid stealing focus from graph navigation.

## Implementation Notes

- Prefer reusing `frontend/src/data/links.ts` for all Bangumi URLs.
- Prefer extracting repeated UI tokens into shared constants once the current prototype stabilizes.
- Keep CSS utility classes close to existing Tailwind usage until repeated patterns justify components.
- Do not introduce visual changes that require reprocessing data unless the data semantics demand it.
