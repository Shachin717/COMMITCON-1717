import { test, expect } from "@playwright/test";

test.describe("Dashboard Sidebar Active State & Navigation", () => {
  test.setTimeout(60000);
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

  test("HOD sidebar: clicking every item highlights correctly, including after page refresh", async ({ page }) => {
    // 1. Login as HOD
    await page.goto(`${baseURL}/hod/login`);
    await page.fill("input[type='email']", "hod.cse@git.edu");
    await page.fill("input[type='password']", "Hod@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL(`${baseURL}/hod`);

    // Verify /hod highlights "Overview & Charts"
    const overviewLink = page.locator("aside nav a[href='/hod']");
    await expect(overviewLink).toHaveAttribute("aria-current", "page");

    // Other links must not be active
    const approvalsLink = page.locator("aside nav a[href='/hod/approvals']");
    const labsLink = page.locator("aside nav a[href='/hod/labs']");
    const historyLink = page.locator("aside nav a[href='/hod/history']");

    await expect(approvalsLink).not.toHaveAttribute("aria-current", "page");
    await expect(labsLink).not.toHaveAttribute("aria-current", "page");
    await expect(historyLink).not.toHaveAttribute("aria-current", "page");

    // Click Pending Approvals
    await approvalsLink.click();
    await expect(page).toHaveURL(`${baseURL}/hod/approvals`);
    await expect(approvalsLink).toHaveAttribute("aria-current", "page");
    await expect(overviewLink).not.toHaveAttribute("aria-current", "page");

    // Refresh and verify persistence
    await page.reload();
    await expect(page).toHaveURL(`${baseURL}/hod/approvals`);
    await expect(approvalsLink).toHaveAttribute("aria-current", "page");
    await expect(overviewLink).not.toHaveAttribute("aria-current", "page");

    // Click Department Labs
    await labsLink.click();
    await expect(page).toHaveURL(`${baseURL}/hod/labs`);
    await expect(labsLink).toHaveAttribute("aria-current", "page");
    await expect(overviewLink).not.toHaveAttribute("aria-current", "page");

    // Refresh and verify persistence
    await page.reload();
    await expect(labsLink).toHaveAttribute("aria-current", "page");

    // Click Bookings History
    await historyLink.click();
    await expect(page).toHaveURL(`${baseURL}/hod/history`);
    await expect(historyLink).toHaveAttribute("aria-current", "page");
    await expect(overviewLink).not.toHaveAttribute("aria-current", "page");

    // Refresh and verify persistence
    await page.reload();
    await expect(historyLink).toHaveAttribute("aria-current", "page");

    // Click back to Overview & Charts
    await overviewLink.click();
    await expect(page).toHaveURL(`${baseURL}/hod`);
    await expect(overviewLink).toHaveAttribute("aria-current", "page");
    await expect(historyLink).not.toHaveAttribute("aria-current", "page");
  });

  test("Admin sidebar: clicking every item highlights correctly, including after page refresh", async ({ page }) => {
    // 1. Login as Admin
    await page.goto(`${baseURL}/staff/login`);
    await page.fill("input[type='email']", "admin@git.edu");
    await page.fill("input[type='password']", "Admin@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL(`${baseURL}/admin`);

    const adminItems = [
      { label: "Overview", href: "/admin" },
      { label: "Allocation Insights", href: "/admin/allocation" },
      { label: "Rooms & Catalog", href: "/admin/rooms" },
      { label: "Slots & Timetable", href: "/admin/timetable" },
      { label: "Users & Staff", href: "/admin/users" },
      { label: "Departments", href: "/admin/departments" },
      { label: "Blocks", href: "/admin/blocks" },
      { label: "Booking History", href: "/admin/bookings" },
      { label: "Audit Logs", href: "/admin/audit-logs" },
    ];

    // Initial check for /admin
    const rootLink = page.locator("aside nav a[href='/admin']");
    await expect(rootLink).toHaveAttribute("aria-current", "page");

    for (const item of adminItems) {
      const link = page.locator(`aside nav a[href='${item.href}']`);
      await link.click();
      await expect(page).toHaveURL(`${baseURL}${item.href}`);
      await expect(link).toHaveAttribute("aria-current", "page");

      // Root link should only match exactly
      if (item.href !== "/admin") {
        await expect(rootLink).not.toHaveAttribute("aria-current", "page");
      }

      // Verify after page reload
      await page.reload();
      await expect(page).toHaveURL(`${baseURL}${item.href}`);
      await expect(page.locator(`aside nav a[href='${item.href}']`)).toHaveAttribute("aria-current", "page");
      if (item.href !== "/admin") {
        await expect(page.locator("aside nav a[href='/admin']")).not.toHaveAttribute("aria-current", "page");
      }
    }
  });

  test("Coordinator sidebar: clicking every item highlights correctly, including after page refresh", async ({ page }) => {
    // 1. Login as Coordinator
    await page.goto(`${baseURL}/staff/login`);
    await page.fill("input[type='email']", "coordinator.block_a@git.edu");
    await page.fill("input[type='password']", "Coord@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL(`${baseURL}/coordinator`);

    const coordinatorItems = [
      { label: "Pending Inbox", href: "/coordinator" },
      { label: "Allocation Insights", href: "/coordinator/allocation" },
      { label: "All-Blocks Status", href: "/coordinator/overview" },
      { label: "Block a Room", href: "/coordinator/block-room" },
      { label: "History", href: "/coordinator/history" },
      { label: "Timetable Grid", href: "/coordinator/timetable" },
    ];

    const rootLink = page.locator("aside nav a[href='/coordinator']");
    await expect(rootLink).toHaveAttribute("aria-current", "page");

    for (const item of coordinatorItems) {
      const link = page.locator(`aside nav a[href='${item.href}']`);
      await link.click();
      await expect(page).toHaveURL(`${baseURL}${item.href}`);
      await expect(link).toHaveAttribute("aria-current", "page");

      if (item.href !== "/coordinator") {
        await expect(rootLink).not.toHaveAttribute("aria-current", "page");
      }

      // Verify after page reload
      await page.reload();
      await expect(page.locator(`aside nav a[href='${item.href}']`)).toHaveAttribute("aria-current", "page");
      if (item.href !== "/coordinator") {
        await expect(page.locator("aside nav a[href='/coordinator']")).not.toHaveAttribute("aria-current", "page");
      }
    }
  });

  test("Faculty sidebar: clicking every item highlights correctly, including after page refresh", async ({ page }) => {
    // 1. Login as Faculty
    await page.goto(`${baseURL}/staff/login`);
    await page.fill("input[type='email']", "faculty.cse@git.edu");
    await page.fill("input[type='password']", "Faculty@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL(`${baseURL}/faculty`);

    const rootLink = page.locator("aside nav a[href='/faculty']");
    const bookingsLink = page.locator("aside nav a[href='/faculty/my-bookings']");

    await expect(rootLink).toHaveAttribute("aria-current", "page");
    await expect(bookingsLink).not.toHaveAttribute("aria-current", "page");

    // Click My Bookings
    await bookingsLink.click();
    await expect(page).toHaveURL(`${baseURL}/faculty/my-bookings`);
    await expect(bookingsLink).toHaveAttribute("aria-current", "page");
    await expect(rootLink).not.toHaveAttribute("aria-current", "page");

    // Reload
    await page.reload();
    await expect(bookingsLink).toHaveAttribute("aria-current", "page");
    await expect(rootLink).not.toHaveAttribute("aria-current", "page");

    // Click Search & Book
    await rootLink.click();
    await expect(page).toHaveURL(`${baseURL}/faculty`);
    await expect(rootLink).toHaveAttribute("aria-current", "page");
    await expect(bookingsLink).not.toHaveAttribute("aria-current", "page");
  });

  test("Mobile drawer: active indicator and aria-current work on mobile viewport", async ({ page }) => {
    // Use mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto(`${baseURL}/hod/login`);
    await page.fill("input[type='email']", "hod.cse@git.edu");
    await page.fill("input[type='password']", "Hod@123");
    await page.click("button[type='submit']");
    await expect(page).toHaveURL(`${baseURL}/hod`);

    // Open mobile sidebar drawer
    await page.click("button[aria-label='Open sidebar']");

    // Drawer link should be visible and have aria-current="page"
    const overviewLink = page.locator("aside nav a[href='/hod']");
    await expect(overviewLink).toBeVisible();
    await expect(overviewLink).toHaveAttribute("aria-current", "page");

    // Click Pending Approvals from mobile drawer
    const approvalsLink = page.locator("aside nav a[href='/hod/approvals']");
    await approvalsLink.click();
    await expect(page).toHaveURL(`${baseURL}/hod/approvals`);

    // Re-open mobile sidebar drawer to verify active item
    await page.click("button[aria-label='Open sidebar']");
    await expect(approvalsLink).toBeVisible();
    await expect(approvalsLink).toHaveAttribute("aria-current", "page");
    await expect(overviewLink).not.toHaveAttribute("aria-current", "page");
  });
});

