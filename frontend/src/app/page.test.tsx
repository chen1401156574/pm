import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "@/app/page";
import { initialData } from "@/lib/kanban";
import { loadBoard, saveBoard } from "@/lib/kanbanApi";

vi.mock("@/lib/kanbanApi", () => ({
  loadBoard: vi.fn(),
  saveBoard: vi.fn(),
}));

vi.mock("@/components/KanbanBoard", () => ({
  KanbanBoard: (props: {
    onLogout?: () => void;
    onBoardChange?: (board: typeof initialData) => void;
    onRetryLoad?: () => void;
    onRetrySave?: () => void;
    loadError?: string | null;
    saveError?: string | null;
  }) => (
    <div>
      <h1>Kanban Studio</h1>
      {props.loadError ? <p role="alert">{props.loadError}</p> : null}
      {props.saveError ? <p role="alert">{props.saveError}</p> : null}
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
    </div>
  ),
}));

describe("Sign in gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(loadBoard).mockResolvedValue(initialData);
    vi.mocked(saveBoard).mockResolvedValue(undefined);
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
});
