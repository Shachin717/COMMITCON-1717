import { test, expect } from "@playwright/test";

test.describe("Smart Classroom E2E Core Workflows", () => {
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

  test("a) Student can explore timetable, search availability, and book/cancel flow", async ({ page }) => {
    await page.goto(`${baseURL}/`);
    await expect(page).toHaveTitle(/Smart Classroom/i);

    // Verify timetable section loads
    const timetableSection = page.locator("text=Public Timetable & Room Occupancy");
    await expect(timetableSection).toBeVisible();

    // Verify manage booking section exists for lookup and cancellation
    const manageSection = page.locator("text=Manage Your Booking");
    await expect(manageSection).toBeVisible();

    // Verify Search & Book interface elements are visible
    const searchHeading = page.locator("text=Find & Book a Classroom");
    await expect(searchHeading).toBeVisible();

    const searchBtn = page.locator("button:has-text('Check Real-Time Availability')");
    await expect(searchBtn).toBeVisible();
  });

  test("b) Coordinator login and access dashboard", async ({ page }) => {
    await page.goto(`${baseURL}/staff/login`);

    // Verify login form is present
    await expect(page.locator("text=Staff Portal Sign In")).toBeVisible();

    // Choose coordinator quick select or fill in credentials
    const coordTab = page.locator("button:has-text('Coordinator')");
    if (await coordTab.isVisible()) {
      await coordTab.click();
    } else {
      await page.fill("input[type='email']", "coordinator.block_a@git.edu");
      await page.fill("input[type='password']", "Coord@123");
    }

    // Submit login
    await page.click("button[type='submit']");

    // Expect redirection to coordinator dashboard
    await expect(page).toHaveURL(/.*\/coordinator/);
    await expect(page.locator("text=Block Coordinator Console")).toBeVisible();
  });

  test("c) HOD login and lab approval portal access", async ({ page }) => {
    await page.goto(`${baseURL}/hod/login`);

    // Verify HOD login page is rendered
    await expect(page.locator("text=HOD Portal")).toBeVisible();

    // Fill HOD credentials
    await page.fill("input[type='email']", "hod.cse@git.edu");
    await page.fill("input[type='password']", "Hod@123");

    // Submit login
    await page.click("button[type='submit']");

    // Expect redirection to /hod dashboard
    await expect(page).toHaveURL(/.*\/hod/);
    await expect(page.locator("text=Head of Department Console")).toBeVisible();
  });

  test("d) Login redirect rules and unauthenticated route protection", async ({ page }) => {
    // 1. Visiting protected /admin without credentials redirects to /staff/login?redirect=%2Fadmin
    await page.goto(`${baseURL}/admin`);
    await expect(page).toHaveURL(/.*\/staff\/login.*redirect=%2Fadmin/);

    // 2. Visiting protected /hod without credentials redirects to /hod/login?redirect=%2Fhod
    await page.goto(`${baseURL}/hod`);
    await expect(page).toHaveURL(/.*\/hod\/login.*redirect=%2Fhod/);

    // 3. Visiting protected /coordinator without credentials redirects to /staff/login
    await page.goto(`${baseURL}/coordinator`);
    await expect(page).toHaveURL(/.*\/staff\/login.*redirect=%2Fcoordinator/);

    // 4. Test expired session notice indicator
    await page.goto(`${baseURL}/staff/login?expired=1`);
    await expect(page.locator("text=Your session has expired")).toBeVisible();
  });
});

