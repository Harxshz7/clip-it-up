import { test, expect } from '@playwright/test';

test.describe('Video Upload and Processing Pipeline Smoke Test', () => {
  test('User uploads video directly to storage and monitors 100% progress via SSE', async ({ page }) => {
    // 1. Navigate to landing page
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('Turn long videos into');

    // 2. Click Upload Video button to open modal
    await page.click('button:has-text("Upload Video")');
    await expect(page.locator('h2')).toContainText('Upload Long Video');

    // 3. Upload a sample test video
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('text=Drag and drop your video here');
    const fileChooser = await fileChooserPromise;

    await fileChooser.setFiles({
      name: 'smoke_test_sample.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('dummy mp4 video binary content for smoke test'),
    });

    // 4. Start Upload
    await page.click('button:has-text("Start Upload")');

    // 5. Verify redirection to Video detail page
    await page.waitForURL(/\/videos\/.+/);
    await expect(page.locator('h1')).toContainText('smoke_test_sample.mp4');

    // 6. Verify SSE connection badge
    await expect(page.locator('text=Live SSE Connected, Pipeline Completed')).toBeVisible({ timeout: 15000 });

    // 7. Wait for pipeline progress to reach 100%
    await expect(page.locator('text=100%')).toBeVisible({ timeout: 30000 });
    await expect(page.locator('text=Video Processing Complete! ✨')).toBeVisible({ timeout: 30000 });
  });
});
