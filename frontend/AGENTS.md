# Frontend Agent Notes

## Scope

This directory contains the existing Next.js frontend MVP for the Kanban board demo.
Current state is frontend-only (local in-memory state), without backend persistence or AI chat.

## Stack

- Next.js 16 (`app` router)
- React 19
- TypeScript
- Tailwind CSS 4
- `@dnd-kit` for drag-and-drop
- Vitest + Testing Library for unit tests
- Playwright for end-to-end tests

## Directory Map

- `src/app/page.tsx`
  - Home route entry.
  - Renders `KanbanBoard`.
- `src/components/`
  - `KanbanBoard.tsx`: main board state and handlers (drag, rename, add, delete).
  - `KanbanColumn.tsx`: column shell, drop zone, title edit, list of cards.
  - `KanbanCard.tsx`: sortable card view and remove action.
  - `KanbanCardPreview.tsx`: drag overlay preview.
  - `NewCardForm.tsx`: local form for adding cards.
- `src/lib/kanban.ts`
  - Domain model types (`Card`, `Column`, `BoardData`).
  - Seed data (`initialData`).
  - Card movement logic (`moveCard`).
  - ID helper (`createId`).
- `src/app/globals.css`
  - Global design tokens and base styles.
- `src/test/setup.ts`
  - Vitest test setup.
- `tests/kanban.spec.ts`
  - Playwright scenarios for board load, add card, drag card.

## Current Behavior

- Board is initialized from `initialData` in memory.
- Supports:
  - Renaming column titles.
  - Adding cards per column.
  - Removing cards.
  - Drag-and-drop within and across columns.
- No auth gate yet.
- No backend API integration yet.
- No persistence after refresh.

## Test Commands

From `frontend/`:

```bash
npm install
npm run test:unit
npm run test:e2e
```

Coverage run:

```bash
npm run test:unit -- --coverage
```

## Integration Expectations (next phases)

- Keep `KanbanBoard` focused on UI state orchestration.
- Introduce API client layer before wiring backend endpoints.
- Preserve existing test IDs used by Playwright:
  - `data-testid^="column-"`
  - `data-testid="card-<id>"`
- Maintain visual palette variables from `globals.css` (aligned with project AGENTS.md).
