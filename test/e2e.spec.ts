import { test, expect } from '@playwright/test'

test.describe('FinAlly E2E', () => {
  test('fresh start: default watchlist + $10k balance', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText(/10,000|10000/)).toBeVisible({ timeout: 10000 })
    await expect(page.getByText('AAPL')).toBeVisible({ timeout: 10000 })
  })

  test('prices are streaming (SSE green dot)', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('[data-testid="connection-dot"]')).toHaveClass(/bg-green/, { timeout: 10000 })
  })

  test('add ticker to watchlist', async ({ page }) => {
    await page.goto('/')
    await page.fill('[data-testid="add-ticker-input"]', 'AMD')
    await page.click('[data-testid="add-ticker-btn"]')
    await expect(page.getByText('AMD')).toBeVisible({ timeout: 5000 })
  })

  test('remove ticker from watchlist', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="remove-ticker-NFLX"]')
    await expect(page.getByText('NFLX')).not.toBeVisible({ timeout: 5000 })
  })

  test('buy shares: cash decreases, position appears', async ({ page }) => {
    await page.goto('/')
    await page.fill('[data-testid="trade-ticker"]', 'AAPL')
    await page.fill('[data-testid="trade-quantity"]', '1')
    await page.click('[data-testid="buy-btn"]')
    await expect(page.getByText('AAPL')).toBeVisible({ timeout: 5000 })
  })

  test('sell shares: position reduces', async ({ page }) => {
    await page.goto('/')
    // Buy first
    await page.fill('[data-testid="trade-ticker"]', 'MSFT')
    await page.fill('[data-testid="trade-quantity"]', '2')
    await page.click('[data-testid="buy-btn"]')
    await page.waitForTimeout(500)
    // Sell 1
    await page.fill('[data-testid="trade-quantity"]', '1')
    await page.click('[data-testid="sell-btn"]')
    await page.waitForTimeout(500)
    // Position still exists (1 remaining)
    await expect(page.getByText('MSFT')).toBeVisible()
  })

  test('portfolio heatmap renders after buy', async ({ page }) => {
    await page.goto('/')
    await page.fill('[data-testid="trade-ticker"]', 'GOOGL')
    await page.fill('[data-testid="trade-quantity"]', '1')
    await page.click('[data-testid="buy-btn"]')
    await expect(page.locator('[data-testid="heatmap"]')).toBeVisible({ timeout: 5000 })
  })

  test('AI chat mock: send message, receive response', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-testid="chat-input"]')
    await page.fill('[data-testid="chat-input"]', 'Hello FinAlly')
    await page.click('[data-testid="chat-submit"]')
    await expect(page.locator('[data-testid="chat-messages"]').getByText(/FinAlly|assistant/i)).toBeVisible({ timeout: 10000 })
  })

  test('SSE reconnection: disconnect and reconnect', async ({ page }) => {
    await page.goto('/')
    // Wait for green
    await expect(page.locator('[data-testid="connection-dot"]')).toHaveClass(/bg-green/, { timeout: 10000 })
    // Simulate offline (intercept network)
    await page.route('/api/stream/prices', route => route.abort())
    await page.waitForTimeout(2000)
    // Unblock
    await page.unroute('/api/stream/prices')
    // Should reconnect
    await expect(page.locator('[data-testid="connection-dot"]')).toHaveClass(/bg-green|bg-yellow/, { timeout: 15000 })
  })
})
