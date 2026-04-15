import { type BoardData, type Card, initialData } from "@/lib/kanban";

type ApiCard = {
  id: string;
  title: string;
  details: string;
  order: number;
};

type ApiColumn = {
  id: string;
  title: string;
  card_ids: string[];
  order: number;
};

type ApiBoardState = {
  columns: ApiColumn[];
  cards: ApiCard[];
};

type ApiLoadBoardResponse = {
  version: number;
  state: ApiBoardState;
};

type ApiAIChatResponse = {
  reply: string;
  board_update: ApiBoardState | null;
};

export type AIChatResult = {
  reply: string;
  boardUpdate: BoardData | null;
};

const normalizeBaseUrl = (url: string) => url.replace(/\/$/, "");

const resolveApiBaseUrl = () => {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return normalizeBaseUrl(configuredBaseUrl);
  }

  if (typeof window !== "undefined") {
    const { hostname, port, protocol } = window.location;
    const isLocalHost = hostname === "localhost" || hostname === "127.0.0.1";
    if (isLocalHost && port === "3000") {
      return `${protocol}//${hostname}:8000`;
    }
  }

  return "";
};

const buildApiUrl = (path: string) => `${resolveApiBaseUrl()}${path}`;

const toBoardData = (state: ApiBoardState): BoardData => {
  const cards: Record<string, Card> = {};
  for (const card of state.cards) {
    cards[card.id] = {
      id: card.id,
      title: card.title,
      details: card.details,
    };
  }

  const columns = [...state.columns]
    .sort((a, b) => a.order - b.order)
    .map((column) => ({
      id: column.id,
      title: column.title,
      cardIds: column.card_ids,
    }));

  return { columns, cards };
};

const toApiBoardState = (board: BoardData): ApiBoardState => {
  const columns = board.columns.map((column, index) => ({
    id: column.id,
    title: column.title,
    card_ids: column.cardIds,
    order: index,
  }));

  let order = 0;
  const cards: ApiCard[] = [];
  for (const column of board.columns) {
    for (const cardId of column.cardIds) {
      const card = board.cards[cardId];
      if (!card) {
        continue;
      }
      cards.push({
        id: card.id,
        title: card.title,
        details: card.details,
        order,
      });
      order += 1;
    }
  }

  return { columns, cards };
};

const readErrorMessage = async (response: Response) => {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Ignore JSON parse failure and use fallback message.
  }
  return `Request failed with status ${response.status}`;
};

export const loadBoard = async (): Promise<BoardData> => {
  const response = await fetch(buildApiUrl("/api/kanban"), {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const payload = (await response.json()) as ApiLoadBoardResponse;
  if (!payload?.state?.columns || !payload?.state?.cards) {
    return initialData;
  }
  return toBoardData(payload.state);
};

export const saveBoard = async (board: BoardData): Promise<void> => {
  const response = await fetch(buildApiUrl("/api/kanban"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(toApiBoardState(board)),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
};

export const chatWithAi = async (question: string): Promise<AIChatResult> => {
  const response = await fetch(buildApiUrl("/api/ai/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const payload = (await response.json()) as ApiAIChatResponse;
  if (typeof payload?.reply !== "string" || !payload.reply.trim()) {
    throw new Error("AI response is missing reply content.");
  }

  return {
    reply: payload.reply,
    boardUpdate: payload.board_update ? toBoardData(payload.board_update) : null,
  };
};

export const __testables = {
  toBoardData,
  toApiBoardState,
  resolveApiBaseUrl,
};
