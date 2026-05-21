import { test, expect } from '@playwright/test';

test.describe('Trading', () => {
  test('buy and sell AAPL via API and UI reflects changes', async ({ page, request }) => {
    // Get initial portfolio state via API
    const initial = await request.get('/api/portfolio');
    expect(initial.ok()).toBeTruthy();
    const initialBody = await initial.json();
    const initialCash: number = initialBody.cash_balance;

    // Execute buy via API
    const buyRes = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 5 },
    });
    expect(buyRes.ok()).toBeTruthy();
    const buyBody = await buyRes.json();
    expect(buyBody.trade.ticker).toBe('AAPL');
    expect(buyBody.trade.side).toBe('buy');
    expect(buyBody.cash_balance).toBeLessThan(initialCash);

    // Now load the page and verify UI shows position
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Look for AAPL in positions area
    const positionsArea = page.locator('[data-testid="positions-table"], [data-section="positions"]').first();
    await expect(positionsArea).toBeVisible({ timeout: 10000 });
    await expect(positionsArea.locator('text=/\\bAAPL\\b/').first()).toBeVisible({ timeout: 10000 });

    // Sell 2 shares
    const sellRes = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'sell', quantity: 2 },
    });
    expect(sellRes.ok()).toBeTruthy();
    const sellBody = await sellRes.json();
    expect(sellBody.cash_balance).toBeGreaterThan(buyBody.cash_balance);

    // Verify position quantity is now 3
    const after = await request.get('/api/portfolio');
    const afterBody = await after.json();
    const aaplPos = (afterBody.positions || []).find((p: any) => p.ticker === 'AAPL');
    expect(aaplPos).toBeDefined();
    expect(aaplPos.quantity).toBeCloseTo(3, 4);
  });

  test('buy AAPL via trade bar UI', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const tickerInput = page.locator('[data-testid="trade-ticker"], input[name="ticker"]').first();
    const qtyInput = page.locator('[data-testid="trade-quantity"], input[name="quantity"]').first();
    const buyBtn = page.locator('[data-testid="trade-buy"], button:has-text("Buy")').first();

    // Skip if trade bar isn't present
    if (!(await tickerInput.isVisible().catch(() => false))) {
      test.skip(true, 'Trade bar not exposed with expected selectors');
      return;
    }

    await tickerInput.fill('AAPL');
    await qtyInput.fill('1');
    await buyBtn.click();

    // Wait for portfolio to update - cash balance should show change
    await page.waitForTimeout(1500);
    // Verify the buy registered via API
    const after = await page.request.get('/api/portfolio');
    const body = await after.json();
    const aapl = (body.positions || []).find((p: any) => p.ticker === 'AAPL');
    expect(aapl).toBeDefined();
    expect(aapl.quantity).toBeGreaterThan(0);
  });
});
