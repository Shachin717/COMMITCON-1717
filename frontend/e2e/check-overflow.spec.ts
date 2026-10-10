import { test, expect } from "@playwright/test";

test.describe("Detect Horizontal Overflow on Main Page", () => {
  const baseURL = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";
  const widths = [360, 768, 1280, 1920];
  const themes = ["light", "dark"];

  for (const width of widths) {
    for (const theme of themes) {
      test(`Width: ${width}px | Theme: ${theme}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.emulateMedia({ colorScheme: theme as "light" | "dark" });
        await page.goto(`${baseURL}/`, { waitUntil: "networkidle" });

        // If dark theme, set class on html/documentElement if needed or check theme toggle
        if (theme === "dark") {
          await page.evaluate(() => {
            document.documentElement.classList.add("dark");
          });
        } else {
          await page.evaluate(() => {
            document.documentElement.classList.remove("dark");
          });
        }

        // Wait a bit for animations/renders
        await page.waitForTimeout(500);

        const overflowInfo = await page.evaluate(() => {
          const docEl = document.documentElement;
          const body = document.body;
          const docScrollWidth = docEl.scrollWidth;
          const docClientWidth = docEl.clientWidth;
          const bodyScrollWidth = body.scrollWidth;
          const bodyClientWidth = body.clientWidth;
          const innerWidth = window.innerWidth;

          const overflowingElements: any[] = [];
          const all = document.querySelectorAll("*");
          all.forEach((el) => {
            const rect = el.getBoundingClientRect();
            // Check if element extends past viewport or has overflowing children
            if (rect.right > innerWidth + 1 || rect.width > innerWidth + 1) {
              const tag = el.tagName.toLowerCase();
              const id = el.id ? `#${el.id}` : "";
              const className = typeof el.className === "string" ? el.className.split(" ").slice(0, 5).join(" ") : "";
              overflowingElements.push({
                tag,
                id,
                className,
                rect: {
                  left: Math.round(rect.left),
                  right: Math.round(rect.right),
                  width: Math.round(rect.width),
                },
                scrollWidth: el.scrollWidth,
                clientWidth: el.clientWidth,
                textSnippet: el.textContent?.slice(0, 30).trim(),
              });
            }
          });

          return {
            docScrollWidth,
            docClientWidth,
            bodyScrollWidth,
            bodyClientWidth,
            innerWidth,
            hasOverflow: docScrollWidth > docClientWidth || bodyScrollWidth > innerWidth,
            overflowingElements,
          };
        });

        console.log(
          `\n[RESULT] Width: ${width}px | Theme: ${theme} | docScrollWidth: ${overflowInfo.docScrollWidth} vs clientWidth: ${overflowInfo.docClientWidth} | innerWidth: ${overflowInfo.innerWidth}`
        );

        if (overflowInfo.overflowingElements.length > 0) {
          console.log(`Found ${overflowInfo.overflowingElements.length} overflowing elements:`);
          for (const item of overflowInfo.overflowingElements.slice(0, 15)) {
            console.log(
              ` - ${item.tag}${item.id} [${item.className}] right=${item.rect.right}px, width=${item.rect.width}px (snippet: "${item.textSnippet}")`
            );
          }
        } else {
          console.log(`No overflowing elements found.`);
        }

        // Verify page cannot scroll horizontally
        const canScrollHorizontally = await page.evaluate(() => {
          const initial = window.scrollX;
          window.scrollTo(9999, window.scrollY);
          const scrolled = window.scrollX;
          window.scrollTo(0, window.scrollY);
          return scrolled > 0;
        });

        expect(overflowInfo.docScrollWidth).toBeLessThanOrEqual(overflowInfo.docClientWidth);
        expect(canScrollHorizontally).toBe(false);
      });
    }
  }
});

