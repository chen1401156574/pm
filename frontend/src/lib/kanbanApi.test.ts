import { initialData } from "@/lib/kanban";
import { __testables, chatWithAi, loadBoard, saveBoard } from "@/lib/kanbanApi";

const createJsonResponse = (payload: unknown, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("kanbanApi", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads board data from API and maps structure", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createJsonResponse({
        version: 1,
        state: {
          columns: [{ id: "col-1", title: "Todo", card_ids: ["card-1"], order: 0 }],
          cards: [{ id: "card-1", title: "Task", details: "Detail", order: 0 }],
        },
      })
    );

    const board = await loadBoard();

    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/kanban$/);
    expect(board.columns[0]).toEqual({
      id: "col-1",
      title: "Todo",
      cardIds: ["card-1"],
    });
    expect(board.cards["card-1"]).toEqual({
      id: "card-1",
      title: "Task",
      details: "Detail",
    });
  });

  it("saves board data using backend schema", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(createJsonResponse({ version: 2, status: "success" }));

    await saveBoard(initialData);

    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/kanban$/);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      })
    );

    const [, requestInit] = fetchSpy.mock.calls[0];
    const payload = JSON.parse(String(requestInit?.body));
    expect(payload.columns[0]).toHaveProperty("card_ids");
    expect(payload.cards[0]).toHaveProperty("order");
  });

  it("keeps only cards referenced by columns when creating API payload", () => {
    const board = {
      ...initialData,
      cards: {
        ...initialData.cards,
        orphan: { id: "orphan", title: "Orphan", details: "Should not be posted" },
      },
    };

    const payload = __testables.toApiBoardState(board);
    const ids = payload.cards.map((card) => card.id);
    expect(ids).not.toContain("orphan");
  });

  it("uses localhost:8000 as fallback API base in local dev", () => {
    expect(__testables.resolveApiBaseUrl()).toBe("http://localhost:8000");
  });

  it("calls AI chat endpoint and maps board_update", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createJsonResponse({
        reply: "updated",
        board_update: {
          columns: [{ id: "col-1", title: "Todo", card_ids: ["card-1"], order: 0 }],
          cards: [{ id: "card-1", title: "Task", details: "Detail", order: 0 }],
        },
      })
    );

    const result = await chatWithAi("add task");
    const [url] = fetchSpy.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/ai\/chat$/);
    expect(result.reply).toBe("updated");
    expect(result.boardUpdate?.cards["card-1"]?.title).toBe("Task");
  });

  it("throws when AI response misses reply", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createJsonResponse({
        board_update: null,
      })
    );

    await expect(chatWithAi("hello")).rejects.toThrow(/missing reply/i);
  });
});
