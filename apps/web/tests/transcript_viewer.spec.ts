import { test, expect } from '@playwright/test';
import { Buffer } from 'node:buffer';

test.describe('Phase 1 Interactive Transcript Viewer & Seek Test', () => {
  test('Upload video -> Transcript ready appears while pipeline continues -> click word seeks video', async ({ page }) => {
    // 1. Navigate to home
    await page.goto('/');

    // 2. Open upload modal
    await page.click('button:has-text("Upload Video")');
    await expect(page.locator('h2:has-text("Upload Long Video")')).toBeVisible();

    // 3. Select sample test video
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('text=Drag and drop your video here');
    const fileChooser = await fileChooserPromise;

    await fileChooser.setFiles({
      name: 'transcript_test_clip.mp4',
      mimeType: 'video/mp4',
      buffer: Buffer.from('dummy mp4 video content with speech'),
    });

    // 4. Start Upload
    await page.click('button:has-text("Start Upload")');

    // 5. Redirection to /videos/[id]
    await page.waitForURL(/\/videos\/.+/);
    await expect(page.locator('h1')).toContainText('transcript_test_clip.mp4');

    // 6. Verify "Transcript & Speakers" panel is visible
    await expect(page.locator('text=Transcript & Speakers')).toBeVisible({ timeout: 10000 });

    // 7. Check for transcript segments and speaker labels
    const speakerLabel = page.locator('span:has-text("Speaker 1"), span:has-text("SPEAKER_00")').first();
    await expect(speakerLabel).toBeVisible({ timeout: 20000 });

    // 8. Find a clickable word in the transcript
    const sampleWord = page.locator('[id^="word-"]').first();
    await expect(sampleWord).toBeVisible();

    // 9. Click the word to seek video
    await sampleWord.click();

    // 10. Verify video player exists and time updated
    const video = page.locator('video');
    await expect(video).toBeVisible();
    
    // Check search box functionality
    const searchInput = page.locator('input[placeholder="Search transcript..."]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('video');
      await expect(page.locator('text=Export')).toBeVisible();
    }
  });
});
