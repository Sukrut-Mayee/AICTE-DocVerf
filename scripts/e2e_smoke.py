"""Headless smoke test for the officer dashboard.

Prerequisites:
  - API on http://localhost:8000 with a throwaway officer database
  - web app on http://localhost:3000

Run: .venv/Scripts/python -m scripts.e2e_smoke
Uses an installed Edge/Chrome via Playwright (no browser download required).
"""

from __future__ import annotations

import sys

from playwright.sync_api import Page, expect, sync_playwright

WEB = "http://localhost:3000"
APP_ID = "app001"
HIGH_IDS = ["f_1a2b3c4d", "f_2b3c4d5e", "f_3c4d5e6f", "f_4d5e6f70"]


def _confirm(page: Page, finding_id: str) -> None:
    card = page.locator(f"#finding-{finding_id}")
    expect(card).to_be_visible()
    card.get_by_role("button", name="Confirm finding").click()
    card.get_by_placeholder(
        "Explain what you checked and why you are confirming or dismissing this finding."
    ).fill(f"E2E: reviewed supporting evidence for {finding_id}.")
    card.get_by_role("button", name="Save confirm").click()
    expect(card.get_by_text("Confirmed", exact=True)).to_be_visible(timeout=15_000)


def run() -> int:
    console_errors: list[str] = []
    page_errors: list[str] = []
    not_found: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1100})
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: not_found.append(response.url) if response.status == 404 else None,
        )

        page.goto(f"{WEB}/officer", wait_until="domcontentloaded", timeout=120_000)
        expect(page.get_by_role("heading", name="Applications awaiting review")).to_be_visible(
            timeout=60_000
        )
        expect(page.get_by_text("Shree Vidya Institute of Technology").first).to_be_visible()
        page.screenshot(path="data/e2e_queue.png", full_page=True)
        print("queue: ok")

        page.locator(f'a[href="/officer/applications/{APP_ID}"]').first.click()
        page.wait_for_url(f"**/officer/applications/{APP_ID}", timeout=60_000)
        expect(
            page.get_by_role("heading", name="Shree Vidya Institute of Technology")
        ).to_be_visible(timeout=60_000)
        expect(page.get_by_text("Decision locked")).to_be_visible()
        expect(page.get_by_text("Choose an outcome")).to_be_visible()

        page.wait_for_selector("canvas", timeout=60_000)
        boxes = page.locator("button[data-evidence-box]")
        expect(boxes.first).to_be_visible(timeout=30_000)
        box_count = boxes.count()
        print(f"pdf: canvas rendered, {box_count} evidence boxes on page 1")
        if box_count < 1:
            raise AssertionError("expected at least one evidence box")
        page.screenshot(path="data/e2e_detail_initial.png", full_page=True)

        _confirm(page, HIGH_IDS[0])
        expect(page.get_by_text("Decision locked")).to_be_visible()
        for finding_id in HIGH_IDS[1:]:
            _confirm(page, finding_id)

        expect(page.get_by_text("Decision locked")).to_have_count(0, timeout=15_000)
        expect(page.get_by_text("Choose an outcome")).to_be_visible()

        page.get_by_role("button").filter(
            has_text="Reject the application. A reason is required."
        ).click()
        page.get_by_role("button", name="Record decision").click()
        expect(
            page.get_by_text("A reason is required when rejecting an application.")
        ).to_be_visible()

        page.locator("#decision-reason").fill(
            "E2E: land ownership could not be established from the reviewed documents."
        )
        page.get_by_role("button", name="Record decision").click()
        expect(page.get_by_text("Decision recorded", exact=True).first).to_be_visible(
            timeout=20_000
        )

        page.reload(wait_until="domcontentloaded")
        expect(page.get_by_text("Recorded decision").first).to_be_visible(timeout=60_000)
        expect(page.get_by_text("Reject", exact=True).first).to_be_visible()
        expect(
            page.get_by_text(
                "E2E: land ownership could not be established from the reviewed documents."
            ).first
        ).to_be_visible()
        expect(page.get_by_text("Confirmed", exact=True).first).to_be_visible()
        page.screenshot(path="data/e2e_detail_final.png", full_page=True)
        print("actions + decision + reload: ok")

        browser.close()

    relevant = [
        error
        for error in console_errors
        if "worker" in error.lower() or "pdf" in error.lower() or "failed" in error.lower()
    ]
    if page_errors or relevant:
        print("page errors:", page_errors)
        print("relevant console errors:", relevant)
        print("404 responses:", not_found)
        return 1
    print("browser console: no page errors")
    if not_found:
        print("404 responses:", not_found)
    return 0


if __name__ == "__main__":
    sys.exit(run())
