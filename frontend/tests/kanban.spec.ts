import { expect, test, type Page } from "@playwright/test";

const login = async (page: Page) => {
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

test("loads the kanban board", async ({ page }) => {
  await login(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await login(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("moves a card between columns", async ({ page }) => {
  await login(page);
  const card = page.getByTestId("card-card-1");
  const targetColumn = page.getByTestId("column-col-review");
  const cardBox = await card.boundingBox();
  const columnBox = await targetColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    columnBox.x + columnBox.width / 2,
    columnBox.y + 120,
    { steps: 12 }
  );
  await page.mouse.up();
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("logs out back to sign in form", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
});

test("applies AI board_update and shows AI reply", async ({ page }) => {
  const boardState = {
    columns: [
      { id: "col-backlog", title: "Backlog", card_ids: ["card-1"], order: 0 },
      { id: "col-discovery", title: "Discovery", card_ids: [], order: 1 },
      { id: "col-progress", title: "In Progress", card_ids: [], order: 2 },
      { id: "col-review", title: "Review", card_ids: [], order: 3 },
      { id: "col-done", title: "Done", card_ids: [], order: 4 },
    ],
    cards: [{ id: "card-1", title: "Seed Task", details: "seed", order: 0 }],
  };

  await page.route("**/api/kanban", async (route) => {
    const request = route.request();
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ version: 1, state: boardState }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/api/ai/chat", async (route) => {
    boardState.cards.push({
      id: "card-2",
      title: "AI Added",
      details: "from ai",
      order: 1,
    });
    boardState.columns[0].card_ids.push("card-2");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reply: "Added one task",
        board_update: boardState,
        version: 2,
      }),
    });
  });

  await login(page);
  await page.getByPlaceholder(/ask ai to update your board/i).fill("please add one task");
  await page.getByRole("button", { name: /^send$/i }).click();
  await expect(page.getByText("Added one task")).toBeVisible();
  await expect(page.getByTestId("column-col-backlog").getByText("AI Added")).toBeVisible();
});
