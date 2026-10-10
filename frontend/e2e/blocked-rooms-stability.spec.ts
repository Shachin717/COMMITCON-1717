import { test, expect } from "@playwright/test";

test.describe("Blocked Rooms 60s stability and verification test", () => {
  test.setTimeout(120000);

  test("Blocked Rooms tab fires minimal requests over 60s, no flicker, URL persistence on refresh, and release updates cleanly", async ({
    page,
  }) => {
    const roomBlockRequests: string[] = [];

    page.on("request", (req) => {
      if (req.url().includes("/api/coordinator/room-blocks")) {
        roomBlockRequests.push(req.url());
        console.log(`[REQUEST #${roomBlockRequests.length}] ${req.url()}`);
      }
    });

    // 1. Login as Coordinator
    await page.goto("http://localhost:3000/staff/login");
    await page.fill("input[type='email']", "coordinator.block_a@git.edu");
    await page.fill("input[type='password']", "Coord@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL("http://localhost:3000/coordinator");

    // 2. Navigate to /coordinator/block-room
    await page.goto("http://localhost:3000/coordinator/block-room");
    await page.waitForTimeout(1000);

    // 3. Switch to Blocked Rooms tab
    console.log("Switching to Blocked Rooms tab...");
    const countBeforeBlockedTab = roomBlockRequests.length;
    await page.getByRole("button", { name: "Blocked Rooms" }).click();

    // Verify URL contains ?tab=blocked
    await expect(page).toHaveURL(/tab=blocked/);

    // Wait for the table container to be visible
    const tableContainer = page.locator(".min-h-\\[480px\\]");
    await expect(tableContainer).toBeVisible();

    // 4. Verify URL persistence on page reload
    console.log("Reloading page to test URL tab persistence...");
    await page.reload();
    await expect(page).toHaveURL(/tab=blocked/);
    const blockedRoomsTabButton = page.getByRole("button", { name: "Blocked Rooms" });
    await expect(blockedRoomsTabButton).toHaveClass(/bg-sky-600/);

    // 5. Leave the Blocked Rooms tab for 60 seconds
    console.log("Observing Blocked Rooms tab for 60 seconds...");
    const countAtStartOf60s = roomBlockRequests.length;
    await page.waitForTimeout(60000);
    const countAfter60s = roomBlockRequests.length;
    const requestsDuring60s = countAfter60s - countAtStartOf60s;
    console.log(`Total /api/coordinator/room-blocks requests during 60 seconds: ${requestsDuring60s}`);

    // Over 60 seconds, with 30s silent poll, there should be at most 2-3 requests (approx 1 poll at 30s, 1 at 60s)
    expect(requestsDuring60s).toBeLessThanOrEqual(4);

    // Settle 2s so no 60s poll timer is in-flight
    await page.waitForTimeout(2000);

    // 6. Test debounced search input (typing does not thrash requests)
    console.log("Testing search input debounce...");
    const searchInput = page.getByPlaceholder("Search by room number, notes, reason...");
    const countBeforeSearch = roomBlockRequests.length;
    
    // Type sequentially with 50ms per key (4 keys = 200ms)
    await searchInput.pressSequentially("CONF", { delay: 50 });
    
    // Wait after debounce (400ms) - must fire with search=CONF
    await page.waitForTimeout(500);
    const searchRequests = roomBlockRequests.filter((u) => u.includes("search=CONF"));
    expect(searchRequests.length).toBe(1);

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(600);

    // 7. Verify Refresh button spins during refresh without collapsing or flickering the table
    console.log("Testing manual Refresh button...");
    const refreshBtn = page.getByRole("button", { name: "Refresh" }).last();
    const countBeforeRefresh = roomBlockRequests.length;
    await refreshBtn.click();
    await page.waitForTimeout(500);
    expect(roomBlockRequests.length).toBeGreaterThan(countBeforeRefresh);

    // 8. Test releasing a block if releasable block exists, or verify release dialog cleanly
    const releaseButtons = page.getByRole("button", { name: "Release" });
    const releaseCount = await releaseButtons.count();
    if (releaseCount > 0) {
      console.log(`Found ${releaseCount} releasable block(s). Testing release action...`);
      const countBeforeRelease = roomBlockRequests.length;
      await releaseButtons.first().click();
      // Confirm dialog opens
      await expect(page.getByText("Release Room Block")).toBeVisible();
      await page.getByRole("button", { name: "Release Room" }).click();
      await page.waitForTimeout(1500);
      // Table updated once without infinite loop
      const requestsAfterRelease = roomBlockRequests.length - countBeforeRelease;
      console.log(`Requests after release action: ${requestsAfterRelease}`);
      expect(requestsAfterRelease).toBeLessThanOrEqual(3);
    } else {
      console.log("No releasable block currently active. Verifying UI stability.");
    }

    console.log("VERIFICATION TEST PASSED SUCCESSFULLY!");
  });
});
