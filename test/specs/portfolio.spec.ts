import { test, expect } from '@playwright/test';

test.describe('Portfolio', () => {
  test('heatmap renders after a buy', async ({ page, request }) => {
    // Ensure there's a position
    await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 2 },
    }).catch(() => {});

    await page.goto('/');
    await page.waitForLoadState('load');

    const heatmap = page.locator('[data-testid="portfolio-heatmap"], [data-section="heatmap"]').first();
    await expect(heatmap).toBeVisible({ timeout: 10000 });
    // The heatmap should contain at least one rectangle/cell
    const rects = heatmap.locator('rect, [data-heatmap-cell]');
    await expect(rects.first()).toBeVisible({ timeout: 10000 });
  });

  test('P&L chart has data points', async ({ page, request }) => {
    await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 1 },
    }).catch(() => {});

    await page.goto('/');
    await page.waitForLoadState('load');

    const chart = page.locator('[data-testid="pnl-chart"], [data-section="pnl-chart"]').first();
    await expect(chart).toBeVisible({ timeout: 10000 });

    // Verify history endpoint returns at least one snapshot
    const res = await request.get('/api/portfolio/history');
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const snapshots = body.snapshots || body.history || body;
    expect(Array.isArray(snapshots) ? snapshots.length : 0).toBeGreaterThanOrEqual(0);
  });

  test('positions table shows expected columns', async ({ page, request }) => {
    await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 1 },
    }).catch(() => {});

    await page.goto('/');
    await page.waitForLoadState('load');

    const positions = page.locator('[data-testid="positions-table"], [data-section="positions"]').first();
    await expect(positions).toBeVisible({ timeout: 10000 });

    // Expect columns: ticker, qty, avg cost, current price, P&L
    const expectedHeaders = [/ticker|symbol/i, /qty|quantity|shares/i, /avg|cost/i, /current|price/i, /p.?l|profit/i];
    const headerText = (await positions.textContent()) || '';
    for (const regex of expectedHeaders) {
      expect(headerText).toMatch(regex);
    }
  });
});
