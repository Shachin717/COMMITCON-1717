import { test, expect } from "@playwright/test";

test.describe("Faculty Classroom Search, Booking & Cancellation Workflow", () => {
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

  test("Faculty user can search availability, book a classroom with prefilled details, and cancel booking", async ({
    page,
  }) => {
    const availabilityRequests: { url: string; status: number }[] = [];
    const bookingRequests: { url: string; status: number }[] = [];
    const cancelRequests: { url: string; status: number }[] = [];

    page.on("response", async (response) => {
      const url = response.url();
      if (url.includes("/availability")) {
        availabilityRequests.push({ url, status: response.status() });
      }
      if (url.includes("/faculty/bookings") && response.request().method() === "POST") {
        if (url.includes("/cancel")) {
          cancelRequests.push({ url, status: response.status() });
        } else {
          bookingRequests.push({ url, status: response.status() });
        }
      }
    });

    // 1. Log in as a Faculty member
    await page.goto(`${baseURL}/staff/login`);
    await page.fill("input[type='email']", "faculty.cse@git.edu");
    await page.fill("input[type='password']", "Faculty@123");
    await page.click("button[type='submit']");

    // 2. Verify redirect to /faculty
    await page.waitForURL("**/faculty**");
    await expect(page.locator("text=Faculty Academic Portal")).toBeVisible();

    // 3. Verify search component is loaded with slot chips
    const periodButtons = page.locator("button:has-text('Period 1')");
    await expect(periodButtons).toBeVisible({ timeout: 10000 });

    // 4. Set search parameters: choose a date 5 days in the future to avoid any conflicts
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + 5);
    const dateStr = targetDate.toISOString().split("T")[0];

    const dateInput = page.locator("input[type='date']");
    await dateInput.fill(dateStr);

    // Click Period 1 if not already selected
    const period1Btn = page.locator("button:has-text('Period 1')").first();
    const isSelected = await period1Btn.locator("text=✓").isVisible();
    if (!isSelected) {
      await period1Btn.click();
    }

    // Trigger search
    const searchBtn = page.locator("button:has-text('Search Available Rooms')");
    await searchBtn.click();

    // 5. Verify availability API was called and rooms are rendered
    await page.waitForTimeout(2000);
    expect(availabilityRequests.length).toBeGreaterThan(0);
    const lastAvailReq = availabilityRequests[availabilityRequests.length - 1];
    expect(lastAvailReq.status).toBe(200);
    expect(lastAvailReq.url).toContain(`date=${dateStr}`);
    expect(lastAvailReq.url).toContain("slot_ids=");

    // Verify room results are visible on the page
    const bookButtons = page.locator("button:has-text('Book as Faculty')");
    const count = await bookButtons.count();
    expect(count).toBeGreaterThan(0);

    // 6. Click 'Book as Faculty' on the first available room
    await bookButtons.first().click();

    // 7. Verify booking modal opened
    const venueIndicator = page.locator("text=Selected Venue");
    await expect(venueIndicator).toBeVisible({ timeout: 5000 });

    // Click continue to faculty details
    const continueBtn = page.locator("button:has-text('Continue to Faculty Details')");
    await continueBtn.click();

    // 8. Verify faculty details are prefilled
    const emailInput = page.locator("input[type='email']");
    await expect(emailInput).toHaveValue("faculty.cse@git.edu");

    const nameInput = page.locator("input[placeholder*='Amit Roy'], input[placeholder*='Jane Doe']");
    await expect(nameInput).toHaveValue("Dr. Amit Roy");

    // Enter purpose
    const purposeInput = page.locator("input[placeholder*='Seminar'], input[placeholder*='Workshop']");
    await purposeInput.fill("Automated Algorithms Verification Lecture");

    // 9. Submit booking request
    const submitBtn = page.locator("button:has-text('Submit Faculty Booking Request')");
    await submitBtn.click();

    // 10. Verify successful booking acknowledgement
    await expect(page.locator("text=Request Successfully Submitted")).toBeVisible({ timeout: 10000 });
    expect(bookingRequests.length).toBeGreaterThan(0);
    expect(bookingRequests[0].status).toBe(201);

    // Get the generated booking reference
    const refCodeElement = page.locator("span.font-mono");
    await expect(refCodeElement).toBeVisible();
    const reference = (await refCodeElement.textContent())?.trim();
    expect(reference).toMatch(/^BK-[A-Z0-9]+$/);
    console.log("Successfully created faculty booking reference:", reference);

    // Close the booking modal by clicking Done & Return to Portal
    const doneBtn = page.locator("button:has-text('Done & Return to Portal')");
    await doneBtn.click();

    // 11. Navigate to 'My Bookings' tab
    const myBookingsTab = page.locator("button:has-text('My Bookings')");
    await myBookingsTab.click();

    // Verify the booking reference is listed in the bookings table
    const bookingRow = page.locator(`tr:has-text('${reference}')`);
    await expect(bookingRow).toBeVisible({ timeout: 10000 });
    await expect(bookingRow.locator("text=Pending")).toBeVisible();

    // 12. Cancel the booking
    const cancelBtn = bookingRow.locator("button:has-text('Cancel Booking')");
    await expect(cancelBtn).toBeVisible();
    await cancelBtn.click();

    // Confirm cancellation in dialog
    const confirmCancelBtn = page.locator("button:has-text('Confirm Cancellation')");
    await expect(confirmCancelBtn).toBeVisible();
    await confirmCancelBtn.click();

    // Verify cancellation API was called successfully
    await page.waitForTimeout(2000);
    expect(cancelRequests.length).toBeGreaterThan(0);
    expect(cancelRequests[0].status).toBe(200);

    // Verify booking row status updated to CANCELLED
    const cancelledBadge = bookingRow.getByText("CANCELLED", { exact: true });
    await expect(cancelledBadge).toBeVisible({ timeout: 10000 });
    console.log("Successfully cancelled faculty booking reference:", reference);
  });
});
