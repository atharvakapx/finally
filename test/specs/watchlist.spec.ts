import { test, expect } from '@playwright/test';

const DEFAULT_TICKERS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'NFLX'];

test.describe('Watchlist', () => {
  test.beforeEach(async ({ request }) => {
    // Best-effort cleanup of any previously added test tickers
    await request.delete('/api/watchlist/PYPL').catch(() => {});
  });

  test('default 10 tickers visible in watchlist', async ({ page }) => {
    await page.goto('/');
    // Wait for watchlist data to load
    await page.waitForLoadState('networkidle');

    for (const ticker of DEFAULT_TICKERS) {
      const locator = page.locator(`text=/\\b${ticker}\\b/`).first();
      await expect(locator).toBeVisible({ timeout: 10000 });
    }
  });

  test('prices update via SSE within 5 seconds', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Capture a price for AAPL, then wait for it to change
    const aaplRow = page.locator('[data-ticker="AAPL"]').first();
    const initialText = await aaplRow.textContent({ timeout: 10000 }).catch(() => '');

    // Wait for any flash class or text change within 5s
    await page.waitForFunction(
      (initial) => {
        const el = document.querySelector('[data-ticker="AAPL"]');
        if (!el) return false;
        return el.textContent !== initial;
      },
      initialText,
      { timeout: 5000 },
    );
  });

  test('connection status dot is green', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const dot = page.locator('[data-testid="connection-status"]').first();
    await expect(dot).toBeVisible({ timeout: 10000 });
    // Wait for it to become green (data-status="green")
    await expect(dot).toHaveAttribute('data-status', 'green', { timeout: 10000 });
  });

  test('add PYPL ticker appears in watchlist', async ({ page, request }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Add via API (most reliable for E2E)
    const res = await request.post('/api/watchlist', { data: { ticker: 'PYPL' } });
    expect(res.ok()).toBeTruthy();

    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=/\\bPYPL\\b/').first()).toBeVisible({ timeout: 10000 });
  });

  test('remove PYPL ticker disappears from watchlist', async ({ page, request }) => {
    // Ensure PYPL exists first
    await request.post('/api/watchlist', { data: { ticker: 'PYPL' } }).catch(() => {});

    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=/\\bPYPL\\b/').first()).toBeVisible({ timeout: 10000 });

    // Remove via API
    const res = await request.delete('/api/watchlist/PYPL');
    expect(res.ok()).toBeTruthy();

    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=/\\bPYPL\\b/').first()).not.toBeVisible({ timeout: 5000 });
  });
});
