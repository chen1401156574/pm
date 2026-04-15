"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { createId, initialData, moveCard, type BoardData, type Card } from "@/lib/kanban";

type KanbanBoardProps = {
  onLogout?: () => void;
  board?: BoardData;
  onBoardChange?: (nextBoard: BoardData) => void;
  isLoading?: boolean;
  loadError?: string | null;
  isSaving?: boolean;
  saveError?: string | null;
  onRetryLoad?: () => void;
  onRetrySave?: () => void;
  aiMessages?: Array<{ id: string; role: "user" | "assistant"; content: string }>;
  aiInput?: string;
  onAiInputChange?: (nextValue: string) => void;
  onAiSubmit?: (event: FormEvent<HTMLFormElement>) => void;
  isAiSending?: boolean;
  aiError?: string | null;
};

export const KanbanBoard = ({
  onLogout,
  board,
  onBoardChange,
  isLoading = false,
  loadError = null,
  isSaving = false,
  saveError = null,
  onRetryLoad,
  onRetrySave,
  aiMessages = [],
  aiInput = "",
  onAiInputChange,
  onAiSubmit,
  isAiSending = false,
  aiError = null,
}: KanbanBoardProps) => {
  const isCard = (card: Card | undefined): card is Card => Boolean(card);
  const [localBoard, setLocalBoard] = useState<BoardData>(() => board ?? initialData);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);

  const applyBoardUpdate = (updater: (current: BoardData) => BoardData) => {
    setLocalBoard((current) => {
      const nextBoard = updater(current);
      onBoardChange?.(nextBoard);
      return nextBoard;
    });
  };

  useEffect(() => {
    if (board) {
      setLocalBoard(board);
    }
  }, [board]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => localBoard.cards, [localBoard.cards]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    applyBoardUpdate((prev) => ({
      ...prev,
      columns: moveCard(prev.columns, active.id as string, over.id as string),
    }));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    applyBoardUpdate((prev) => ({
      ...prev,
      columns: prev.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    }));
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    applyBoardUpdate((prev) => ({
      ...prev,
      cards: {
        ...prev.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: prev.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    applyBoardUpdate((prev) => {
      return {
        ...prev,
        cards: Object.fromEntries(
          Object.entries(prev.cards).filter(([id]) => id !== cardId)
        ),
        columns: prev.columns.map((column) =>
          column.id === columnId
            ? {
                ...column,
                cardIds: column.cardIds.filter((id) => id !== cardId),
              }
            : column
        ),
      };
    });
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                One board. Five columns. Zero clutter.
              </p>
              {isLoading ? (
                <p className="mt-3 text-xs font-medium text-[var(--gray-text)]">
                  Loading board...
                </p>
              ) : null}
              {isSaving ? (
                <p className="mt-3 text-xs font-medium text-[var(--gray-text)]">
                  Saving changes...
                </p>
              ) : null}
              {loadError ? (
                <div className="mt-3 space-y-2">
                  <p role="alert" className="text-xs font-medium text-red-600">
                    {loadError}
                  </p>
                  {onRetryLoad ? (
                    <button
                      type="button"
                      onClick={onRetryLoad}
                      className="rounded-full border border-red-200 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-red-600"
                    >
                      Retry load
                    </button>
                  ) : null}
                </div>
              ) : null}
              {saveError ? (
                <div className="mt-3 space-y-2">
                  <p role="alert" className="text-xs font-medium text-red-600">
                    {saveError}
                  </p>
                  {onRetrySave ? (
                    <button
                      type="button"
                      onClick={onRetrySave}
                      className="rounded-full border border-red-200 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-red-600"
                    >
                      Retry save
                    </button>
                  ) : null}
                </div>
              ) : null}
              {onLogout ? (
                <button
                  type="button"
                  onClick={onLogout}
                  className="mt-4 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--secondary-purple)] transition hover:border-[var(--secondary-purple)]"
                >
                  Log out
                </button>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {localBoard.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <div className="grid gap-6 lg:grid-cols-5">
              {localBoard.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds
                    .map((cardId) => localBoard.cards[cardId])
                    .filter(isCard)}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </div>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          <aside className="flex h-[calc(100vh-11rem)] min-h-[520px] flex-col rounded-[28px] border border-[var(--stroke)] bg-white/90 p-5 shadow-[var(--shadow)] backdrop-blur">
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
              AI Assistant
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold text-[var(--navy-dark)]">Board Copilot</h2>
            <p className="mt-2 text-xs leading-5 text-[var(--gray-text)]">
              Ask AI to summarize progress or update the board. Changes apply automatically when
              `board_update` is returned.
            </p>

            <div className="mt-4 flex-1 space-y-3 overflow-y-auto rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-3">
              {aiMessages.length === 0 ? (
                <p className="text-xs text-[var(--gray-text)]">
                  Start a conversation, for example: “Create a task to prepare sprint demo.”
                </p>
              ) : null}
              {aiMessages.map((message) => (
                <article
                  key={message.id}
                  className={
                    message.role === "assistant"
                      ? "rounded-2xl bg-white p-3 text-sm text-[var(--navy-dark)]"
                      : "ml-8 rounded-2xl bg-[var(--secondary-purple)] p-3 text-sm text-white"
                  }
                >
                  <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] opacity-80">
                    {message.role === "assistant" ? "AI" : "You"}
                  </p>
                  <p className="whitespace-pre-wrap leading-6">{message.content}</p>
                </article>
              ))}
            </div>

            {aiError ? (
              <p role="alert" className="mt-3 text-xs font-medium text-red-600">
                {aiError}
              </p>
            ) : null}

            <form onSubmit={onAiSubmit} className="mt-3 space-y-2">
              <textarea
                value={aiInput}
                onChange={(event) => onAiInputChange?.(event.target.value)}
                rows={4}
                placeholder="Ask AI to update your board..."
                className="w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm"
                disabled={isAiSending}
              />
              <button
                type="submit"
                disabled={isAiSending || !aiInput.trim()}
                className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isAiSending ? "Sending..." : "Send"}
              </button>
            </form>
          </aside>
        </section>
      </main>
    </div>
  );
};
