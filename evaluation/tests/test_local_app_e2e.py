"""Opt-in end-to-end verification of showcase, mobile layout, audio, evidence, and exit modal teardown
against the live FastAPI application using Playwright.

NOTE: This test suite is explicitly OPT-IN to ensure offline test hermeticity and isolation.
It will NOT run during standard discovery unless RUN_BROWSER_E2E=1 is set.
"""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

# Check if explicitly opted in
OPT_IN = os.environ.get("RUN_BROWSER_E2E") == "1"

PORT = 8899
BASE_URL = f"http://127.0.0.1:{PORT}"


def get_db_url():
    state_path = os.environ.get("EVAL_TEST_STATE")
    if not state_path or not Path(state_path).is_file():
        raise unittest.SkipTest("EVAL_TEST_STATE file required for browser E2E tests")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    dsn = state.get("readonly_dsn")
    if not dsn:
        raise unittest.SkipTest("EVAL_TEST_STATE must define readonly_dsn; admin_dsn is disallowed")
    from evaluation.serve import database_uri
    return database_uri(dsn)


def get_env_with_libs():
    env = os.environ.copy()
    # Optional: extra shared libraries for a locally unpacked headless Chrome.
    chrome_libs = os.environ.get("CHROME_LIBS_DIR")
    if chrome_libs:
        current_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{chrome_libs}:{current_ld}" if current_ld else chrome_libs
    env["DATABASE_URL"] = get_db_url()
    # Strictly scrub model credentials to prevent live outbound traffic
    for k in ["GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GENAI_USE_VERTEXAI"]:
        env.pop(k, None)
    env["GOOGLE_API_KEY"] = "mock-key-do-not-contact-model"
    return env


@unittest.skipUnless(OPT_IN, "Browser E2E tests are opt-in (set RUN_BROWSER_E2E=1)")
class TestLocalAppE2E(unittest.IsolatedAsyncioTestCase):
    server_proc = None

    @classmethod
    def setUpClass(cls):
        if not OPT_IN:
            return

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ]
        cls.server_proc = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[2]),
            env=get_env_with_libs(),
        )

        deadline = time.time() + 10
        ready = False
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                    ready = True
                    break
            except OSError:
                time.sleep(0.2)
        if not ready:
            cls.server_proc.terminate()
            raise RuntimeError("Uvicorn server failed to start within 10s")

    @classmethod
    def tearDownClass(cls):
        if cls.server_proc:
            cls.server_proc.terminate()
            cls.server_proc.wait()

    async def asyncSetUp(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            env=get_env_with_libs(),
        )

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_showcase_mobile_layout_and_criteria_order(self):
        context = await self.browser.new_context(viewport={"width": 375, "height": 667})
        page = await context.new_page()

        await page.goto(f"{BASE_URL}/showcase?example=returning-to-study")
        await page.wait_for_selector(".criteria-banner")

        crit_box = await page.query_selector(".criteria-banner")
        self.assertIsNotNone(crit_box)

        jump_link = await page.query_selector(".mobile-jump-link")
        self.assertIsNotNone(jump_link)
        self.assertTrue(await jump_link.is_visible())

        items = await page.query_selector_all(".criteria-item")
        self.assertEqual(len(items), 3)

        prov_notice = await page.query_selector(".provisional-notice")
        self.assertIsNotNone(prov_notice)
        text = await prov_notice.text_content()
        self.assertIn("Self-review by Hermes", text)

        await context.close()

    async def test_evidence_expansion_and_exact_excerpt(self):
        page = await self.browser.new_page()
        await page.goto(f"{BASE_URL}/showcase?example=returning-to-study")
        await page.wait_for_selector(".evidence-disclosure")

        disclosures = await page.query_selector_all(".evidence-disclosure")
        self.assertGreaterEqual(len(disclosures), 1)

        first_disc = disclosures[0]
        await first_disc.click()

        content = await page.content()
        self.assertIn("Bachelor degree in IT/quantitative field, or 2+ years of professional IT experience", content)
        self.assertNotIn("bachelor degree in any field", content.lower())

        await page.close()

    async def test_audio_elements_valid(self):
        page = await self.browser.new_page()
        await page.goto(f"{BASE_URL}/showcase?example=returning-to-study")
        await page.wait_for_selector("audio")

        audios = await page.query_selector_all("audio")
        self.assertEqual(len(audios), 2)

        for a in audios:
            src = await a.get_attribute("src")
            self.assertTrue(src.endswith(".wav"))
            resp = await page.request.get(f"{BASE_URL}{src}")
            self.assertEqual(resp.status, 200)
            self.assertTrue("wav" in resp.headers.get("content-type", "").lower())

        await page.close()

    async def test_main_app_exit_dialog_teardown(self):
        page = await self.browser.new_page()
        await page.goto(f"{BASE_URL}/")

        link = await page.query_selector("#showcaseFooterLink")
        self.assertIsNotNone(link)

        # Mock active session functions
        await page.evaluate("""() => {
            window.__mockWsClosed = false;
            window.__mockAudioStopped = false;
            window.__mockRecordingStopped = false;
            window.__mockScreenStopped = false;

            window.ws = {
                readyState: WebSocket.OPEN,
                close: function() { window.__mockWsClosed = true; }
            };
            window.stopAgentAudio = function() { window.__mockAudioStopped = true; };
            window.stopRecording = function() { window.__mockRecordingStopped = true; };
            window.stopScreenSharing = function() { window.__mockScreenStopped = true; };
        }""")

        await link.click()

        modal = await page.query_selector("#showcaseExitModal")
        self.assertIsNotNone(modal)
        self.assertTrue(await modal.is_visible())

        # Test cancel
        cancel_btn = await page.query_selector("#exitModalCancelBtn")
        await cancel_btn.click()
        self.assertFalse(await modal.is_visible())

        # Test escape
        await link.click()
        self.assertTrue(await modal.is_visible())
        await page.keyboard.press("Escape")
        self.assertFalse(await modal.is_visible())

        # Test confirm teardown
        await link.click()
        confirm_btn = await page.query_selector("#exitModalConfirmBtn")
        await confirm_btn.click()

        teardown_status = await page.evaluate("""() => ({
            wsClosed: window.__mockWsClosed,
            audioStopped: window.__mockAudioStopped,
            recordingStopped: window.__mockRecordingStopped,
            screenStopped: window.__mockScreenStopped,
            userDisconnect: window.userInitiatedDisconnect
        })""")

        self.assertTrue(teardown_status["wsClosed"])
        self.assertTrue(teardown_status["audioStopped"])
        self.assertTrue(teardown_status["recordingStopped"])
        self.assertTrue(teardown_status["screenStopped"])
        self.assertTrue(teardown_status["userDisconnect"])

        await page.close()


if __name__ == "__main__":
    unittest.main()
