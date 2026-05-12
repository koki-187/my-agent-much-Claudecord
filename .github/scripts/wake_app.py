"""
Streamlit Cloud sleep 状態を自動で解除する keep-alive スクリプト。

GitHub Actions の cron で 30分おきに実行されることを想定。
- ヘッドレス Chrome でアプリURLを開く
- "Yes, get this app back up!" / "はい、このアプリを復旧させてください！" ボタンが
  表示されていればクリックして起動
- アプリが既に稼働中ならアクセスのみで終了
"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright

APP_URL = os.environ.get("APP_URL", "https://my-agent-much.streamlit.app")
TIMEOUT = 60_000   # ページロードタイムアウト (ms)
WAKE_TIMEOUT = 90_000   # スリープから起き上がるまで待つ最大時間 (ms)


async def wake_app() -> int:
    """
    Returns:
        0: 正常 (起動済み or 復旧クリック成功)
        1: タイムアウト等の異常
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 "
                        "MAM-KeepAlive/1.0"),
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()
        try:
            print(f"[keep-alive] navigating: {APP_URL}", flush=True)
            await page.goto(APP_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
            # スリープ判定: "wake up" ボタンを探す（英語版・日本語版両対応）
            wake_button_selectors = [
                'button:has-text("Yes, get this app back up")',
                'button:has-text("はい、このアプリを復旧")',
                'button:has-text("Yes, get this app back up!")',
                'button[kind="primary"]:has-text("はい")',
            ]
            wake_btn = None
            for sel in wake_button_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        wake_btn = btn
                        print(f"[keep-alive] sleep detected via selector: {sel}", flush=True)
                        break
                except Exception:
                    continue

            if wake_btn:
                print("[keep-alive] clicking wake button...", flush=True)
                await wake_btn.click()
                # 復旧後 streamlit がロードされるのを待つ（最大90秒）
                try:
                    await page.wait_for_selector(
                        '[data-testid="stApp"], [data-testid="stAppViewContainer"]',
                        timeout=WAKE_TIMEOUT,
                    )
                    print("[keep-alive] app recovered successfully", flush=True)
                except Exception as e:
                    print(f"[keep-alive] WARN: app element not found after wake "
                          f"(may still be loading): {e}", flush=True)
            else:
                # スリープボタンなし=既に起きている。少し待ってアクティビティとして記録
                await page.wait_for_timeout(5000)
                print("[keep-alive] app already awake, ping recorded", flush=True)

            # ページ最終状態を確認
            title = await page.title()
            url = page.url
            print(f"[keep-alive] final title: {title!r} url: {url}", flush=True)
            return 0
        except Exception as e:
            print(f"[keep-alive] ERROR: {type(e).__name__}: {e}", flush=True)
            return 1
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(wake_app()))
