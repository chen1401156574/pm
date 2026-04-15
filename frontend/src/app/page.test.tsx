import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "@/app/page";
import { initialData } from "@/lib/kanban";
import { chatWithAi, loadBoard, saveBoard } from "@/lib/kanbanApi";

vi.mock("@/lib/kanbanApi", () => ({
  loadBoard: vi.fn(),
  saveBoard: vi.fn(),
  chatWithAi: vi.fn(),
}));

vi.mock("@/components/KanbanBoard", () => ({
  KanbanBoard: (props: {
    onLogout?: () => void;
    onBoardChange?: (board: typeof initialData) => void;
    onRetryLoad?: () => void;
    onRetrySave?: () => void;
    loadError?: string | null;
    saveError?: string | null;
    aiMessages?: Array<{ id: string; role: "user" | "assistant"; content: string }>;
    aiInput?: string;
    onAiInputChange?: (nextValue: string) => void;
    onAiSubmit?: (event: React.FormEvent<HTMLFormElement>) => void;
    isAiSending?: boolean;
    aiError?: string | null;
  }) => (
    <div>
      <h1>Kanban Studio</h1>
      {props.loadError ? <p role="alert">{props.loadError}</p> : null}
      {props.saveError ? <p role="alert">{props.saveError}</p> : null}
      {props.aiError ? <p role="alert">{props.aiError}</p> : null}
      <button type="button" onClick={props.onLogout}>
        Log out
      </button>
      <button type="button" onClick={() => props.onBoardChange?.(initialData)}>
        Trigger change
      </button>
      <button type="button" onClick={props.onRetryLoad}>
        Retry load
      </button>
      <button type="button" onClick={props.onRetrySave}>
        Retry save
      </button>
      <form onSubmit={props.onAiSubmit}>
        <textarea
          aria-label="AI input"
          value={props.aiInput}
          onChange={(event) => props.onAiInputChange?.(event.target.value)}
        />
        <button type="submit" disabled={props.isAiSending}>
          Send
        </button>
      </form>
      <ul>
        {props.aiMessages?.map((message) => (
          <li key={message.id}>{message.content}</li>
        ))}
      </ul>
    </div>
  ),
}));

describe("Sign in gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(loadBoard).mockResolvedValue(initialData);
    vi.mocked(saveBoard).mockResolvedValue(undefined);
    vi.mocked(chatWithAi).mockResolvedValue({
      reply: "done",
      boardUpdate: null,
    });
  });

  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("shows login form before authentication", async () => {
    render(<Home />);
    expect(await screen.findByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /kanban studio/i })).not.toBeInTheDocument();
  });

  it("authenticates with the expected credentials", async () => {
    render(<Home />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username/i), "user");
    await user.type(screen.getByLabelText(/password/i), "password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();
    expect(loadBoard).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /log out/i })).toBeInTheDocument();
  });

  it("shows error for invalid credentials and allows logout after a valid login", async () => {
    render(<Home />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username/i), "wrong");
    await user.type(screen.getByLabelText(/password/i), "credentials");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/invalid credentials/i);

    await user.clear(screen.getByLabelText(/username/i));
    await user.clear(screen.getByLabelText(/password/i));
    await user.type(screen.getByLabelText(/username/i), "user");
    await user.type(screen.getByLabelText(/password/i), "password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await user.click(await screen.findByRole("button", { name: /log out/i }));

    expect(await screen.findByRole("button", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /kanban studio/i })).not.toBeInTheDocument();
  });

  it("supports retry when board loading fails", async () => {
    vi.mocked(loadBoard)
      .mockRejectedValueOnce(new Error("load failed"))
      .mockResolvedValueOnce(initialData);
    render(<Home />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username/i), "user");
    await user.type(screen.getByLabelText(/password/i), "password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("load failed");
    await user.click(screen.getByRole("button", { name: /retry load/i }));
    expect(await screen.findByRole("heading", { name: /kanban studio/i })).toBeInTheDocument();
    expect(loadBoard).toHaveBeenCalledTimes(2);
  });

  it("supports retry when board saving fails", async () => {
    vi.mocked(saveBoard)
      .mockRejectedValueOnce(new Error("save failed"))
      .mockResolvedValueOnce(undefined);

    render(<Home />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username/i), "user");
    await user.type(screen.getByLabelText(/password/i), "password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByRole("heading", { name: /kanban studio/i });

    await user.click(screen.getByRole("button", { name: /trigger change/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("save failed");
    await user.click(screen.getByRole("button", { name: /retry save/i }));
    expect(saveBoard).toHaveBeenCalledTimes(2);
  });

  it("sends AI message and refreshes board when board_update exists", async () => {
    vi.mocked(chatWithAi).mockResolvedValueOnce({
      reply: "updated",
      boardUpdate: initialData,
    });
    vi.mocked(loadBoard).mockResolvedValue(initialData);

    render(<Home />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/username/i), "user");
    await user.type(screen.getByLabelText(/password/i), "password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await screen.findByRole("heading", { name: /kanban studio/i });

    await user.type(screen.getByLabelText(/ai input/i), "add task");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(chatWithAi).toHaveBeenCalledWith("add task");
    expect(await screen.findByText("updated")).toBeInTheDocument();
    expect(loadBoard).toHaveBeenCalledTimes(2);
  });
});
