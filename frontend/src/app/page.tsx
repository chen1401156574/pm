"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { type BoardData } from "@/lib/kanban";
import { chatWithAi, loadBoard, saveBoard } from "@/lib/kanbanApi";

const SESSION_KEY = "pm-authenticated";
const VALID_USERNAME = "user";
const VALID_PASSWORD = "password";
const MAX_AI_MESSAGES = 30;

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export default function Home() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [isBoardLoading, setIsBoardLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastFailedSave, setLastFailedSave] = useState<BoardData | null>(null);
  const [aiMessages, setAiMessages] = useState<ChatMessage[]>([]);
  const [aiInput, setAiInput] = useState("");
  const [isAiSending, setIsAiSending] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    setIsAuthenticated(window.sessionStorage.getItem(SESSION_KEY) === "true");
    setIsReady(true);
  }, []);

  const handleLogin = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (username === VALID_USERNAME && password === VALID_PASSWORD) {
      window.sessionStorage.setItem(SESSION_KEY, "true");
      setError("");
      setPassword("");
      setIsAuthenticated(true);
      return;
    }
    setError("Invalid credentials. Use user / password.");
  };

  const handleLogout = () => {
    window.sessionStorage.removeItem(SESSION_KEY);
    setIsAuthenticated(false);
    setUsername("");
    setPassword("");
    setError("");
    setBoard(null);
    setLoadError(null);
    setSaveError(null);
    setLastFailedSave(null);
    setAiMessages([]);
    setAiInput("");
    setIsAiSending(false);
    setAiError(null);
  };

  const fetchBoard = async () => {
    setIsBoardLoading(true);
    setLoadError(null);
    try {
      const nextBoard = await loadBoard();
      setBoard(nextBoard);
    } catch (fetchError) {
      const message =
        fetchError instanceof Error
          ? fetchError.message
          : "Failed to load board. Please retry.";
      setLoadError(message);
    } finally {
      setIsBoardLoading(false);
    }
  };

  const persistBoard = async (nextBoard: BoardData) => {
    setIsSaving(true);
    setSaveError(null);
    try {
      await saveBoard(nextBoard);
      setLastFailedSave(null);
    } catch (persistError) {
      const message =
        persistError instanceof Error
          ? persistError.message
          : "Failed to save board changes.";
      setSaveError(message);
      setLastFailedSave(nextBoard);
    } finally {
      setIsSaving(false);
    }
  };

  const handleBoardChange = (nextBoard: BoardData) => {
    setBoard(nextBoard);
    void persistBoard(nextBoard);
  };

  const handleRetrySave = () => {
    if (!lastFailedSave) {
      return;
    }
    void persistBoard(lastFailedSave);
  };

  const addMessage = (role: ChatMessage["role"], content: string) => {
    const message: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
    };
    setAiMessages((current) => [...current, message].slice(-MAX_AI_MESSAGES));
  };

  const handleAiSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = aiInput.trim();
    if (!question || isAiSending) {
      return;
    }

    addMessage("user", question);
    setAiInput("");
    setAiError(null);
    setIsAiSending(true);

    try {
      const result = await chatWithAi(question);
      addMessage("assistant", result.reply);
      if (result.boardUpdate) {
        setBoard(result.boardUpdate);
        await fetchBoard();
      }
    } catch (sendError) {
      const message =
        sendError instanceof Error
          ? sendError.message
          : "Failed to send AI message. Please retry.";
      setAiError(message);
    } finally {
      setIsAiSending(false);
    }
  };

  useEffect(() => {
    if (!isAuthenticated || board !== null || isBoardLoading || loadError !== null) {
      return;
    }
    void fetchBoard();
  }, [isAuthenticated, board, isBoardLoading, loadError]);

  if (!isReady) {
    return null;
  }

  if (isAuthenticated) {
    return (
      <KanbanBoard
        onLogout={handleLogout}
        board={board ?? undefined}
        onBoardChange={handleBoardChange}
        isLoading={isBoardLoading}
        loadError={loadError}
        onRetryLoad={() => void fetchBoard()}
        isSaving={isSaving}
        saveError={saveError}
        onRetrySave={handleRetrySave}
        aiMessages={aiMessages}
        aiInput={aiInput}
        onAiInputChange={setAiInput}
        onAiSubmit={(event) => void handleAiSubmit(event)}
        isAiSending={isAiSending}
        aiError={aiError}
      />
    );
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <section className="w-full rounded-[28px] border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
          PM MVP Sign In
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]">
          Welcome Back
        </h1>
        <p className="mt-2 text-sm text-[var(--gray-text)]">
          Use <strong>user</strong> and <strong>password</strong> to continue.
        </p>
        <form onSubmit={handleLogin} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-[var(--navy-dark)]">
            Username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm"
              autoComplete="username"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--navy-dark)]">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm"
              autoComplete="current-password"
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm font-medium text-red-600">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            className="w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          >
            Sign in
          </button>
        </form>
      </section>
    </main>
  );
}
