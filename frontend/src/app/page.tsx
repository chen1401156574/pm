"use client";

import { FormEvent, useEffect, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";

const SESSION_KEY = "pm-authenticated";
const VALID_USERNAME = "user";
const VALID_PASSWORD = "password";

export default function Home() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);

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
  };

  if (!isReady) {
    return null;
  }

  if (isAuthenticated) {
    return <KanbanBoard onLogout={handleLogout} />;
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
