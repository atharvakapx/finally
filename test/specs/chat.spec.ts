import { test, expect } from '@playwright/test';

test.describe('Chat (LLM_MOCK=true)', () => {
  test('send a message and receive a response', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Open chat panel if needed
    const toggle = page.locator('[data-testid="chat-toggle"], button:has-text("Chat")').first();
    if (await toggle.isVisible().catch(() => false)) {
      await toggle.click().catch(() => {});
    }

    const input = page.locator('[data-testid="chat-input"], textarea[name="chat"], input[name="chat"]').first();
    await expect(input).toBeVisible({ timeout: 10000 });

    await input.fill('What is my portfolio?');

    const submitBtn = page.locator('[data-testid="chat-submit"], button:has-text("Send")').first();
    if (await submitBtn.isVisible().catch(() => false)) {
      await submitBtn.click();
    } else {
      await input.press('Enter');
    }

    // Wait for response message to appear
    const responseArea = page.locator('[data-testid="chat-messages"], [data-section="chat-messages"]').first();
    await expect(responseArea).toBeVisible({ timeout: 10000 });

    // Wait for assistant message
    const assistantMsg = responseArea.locator('[data-role="assistant"], [data-message-role="assistant"]').first();
    await expect(assistantMsg).toBeVisible({ timeout: 15000 });

    const text = (await assistantMsg.textContent()) || '';
    expect(text.trim().length).toBeGreaterThan(0);
  });

  test('chat API returns mock response', async ({ request }) => {
    const res = await request.post('/api/chat', {
      data: { message: 'What is my portfolio?' },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.message).toBeTruthy();
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
  });
});
