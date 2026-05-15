"""
PWA (Progressive Web App) アセット注入モジュール v2

Streamlit には標準で <head> 要素を追加する API がないため、
JavaScript で動的にメタタグ・リンク要素を <head> に挿入する。

対応OS / ブラウザ:
- iOS Safari (apple-touch-icon, standalone, safe-area-inset)
- Android Chrome (manifest, 192/512, BeforeInstallPromptEvent)
- Windows / Edge (msapplication-Tile, browserconfig)
- macOS Safari (mask-icon, apple-touch-icon)
- Edge / Firefox / Chrome (manifest, install prompt)

変更点 (v2):
- Service Worker 登録スクリプトを注入 (Streamlit Cloud 対応)
- PWA インストールプロンプト UI 追加 (Android/Chrome)
- iOS Safari standalone モードでの safe-area-inset padding 追加
- オフライン検出 + 軽量バナー表示
- window.parent.document フォールバック改善
"""
from __future__ import annotations
import base64
import json
import os
from functools import lru_cache
from typing import Optional

import streamlit as st


_LOGO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "mam_logo")
_BRAND_NAME = "My Agent Match"
_BRAND_SHORT = "MAM"
_BRAND_DESC = "不動産仲介プロ向け AI 案件調査・営業判断支援システム"
_THEME_COLOR = "#0A0A0C"        # サイドバー黒
_BG_COLOR = "#0A0A0C"            # スプラッシュ背景


@lru_cache(maxsize=32)
def _b64_png(size: int) -> Optional[str]:
    """指定サイズの mam_NxN.png を base64 data URI で返す。lru_cache で永続キャッシュ"""
    p = os.path.join(_LOGO_DIR, f"mam_{size}x{size}.png")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        b = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b}"


@lru_cache(maxsize=1)
def _build_manifest_cached() -> str:
    return _build_manifest()


def _build_manifest() -> str:
    """PWA Web App Manifest を JSON 文字列で生成"""
    icons = []
    for sz in [192, 256, 384, 512]:
        uri = _b64_png(sz)
        if uri:
            icons.append({
                "src": uri,
                "sizes": f"{sz}x{sz}",
                "type": "image/png",
                "purpose": "any maskable" if sz in (192, 512) else "any",
            })
    manifest = {
        "name": _BRAND_NAME,
        "short_name": _BRAND_SHORT,
        "description": _BRAND_DESC,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "portrait-primary",
        "background_color": _BG_COLOR,
        "theme_color": _THEME_COLOR,
        "lang": "ja",
        "categories": ["business", "productivity", "finance"],
        "icons": icons,
        "shortcuts": [
            {
                "name": "新規案件分析",
                "short_name": "分析",
                "description": "物件情報を入力してAI分析を開始",
                "url": "/?action=new",
            },
            {
                "name": "案件履歴",
                "short_name": "履歴",
                "description": "保存済み案件を確認",
                "url": "/?action=history",
            },
        ],
    }
    return json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))


def inject_pwa_head() -> None:
    """
    PWA 必須メタタグ・アイコンリンク・manifest・Service Worker を <head> に注入する。
    Streamlit のセキュリティ制約上、JavaScript で動的に挿入する。
    """
    manifest_json = _build_manifest_cached()
    manifest_uri = "data:application/manifest+json;charset=utf-8;base64," + \
                   base64.b64encode(manifest_json.encode()).decode()

    icon_180 = _b64_png(180) or _b64_png(192) or _b64_png(256)
    icon_192 = _b64_png(192)
    icon_512 = _b64_png(512)
    icon_32  = _b64_png(32)
    icon_16  = _b64_png(16)
    icon_152 = _b64_png(152)
    icon_167 = _b64_png(167)
    icon_144 = _b64_png(144)

    js = f"""
    <script>
    (function(){{
        // ── ドキュメント取得 (Streamlit iframe 内外どちらでも動作) ──
        var doc = (function() {{
            try {{
                // Streamlit は iframe 内に React を展開する場合がある
                if (window.parent && window.parent.document && window.parent.document !== window.document)
                    return window.parent.document;
            }} catch(e) {{ /* cross-origin */ }}
            return window.document;
        }})();
        var head = doc.head;
        if (!head) return;

        function ensureLink(rel, attrs) {{
            var sel = 'link[rel="' + rel + '"]';
            if (attrs.sizes) sel += '[sizes="' + attrs.sizes + '"]';
            doc.querySelectorAll(sel).forEach(function(el){{ el.remove(); }});
            var l = doc.createElement('link');
            l.rel = rel;
            Object.keys(attrs).forEach(function(k){{ l.setAttribute(k, attrs[k]); }});
            head.appendChild(l);
        }}
        function ensureMeta(name, content, useProperty) {{
            var sel = (useProperty ? 'meta[property="' : 'meta[name="') + name + '"]';
            doc.querySelectorAll(sel).forEach(function(el){{ el.remove(); }});
            var m = doc.createElement('meta');
            if (useProperty) m.setAttribute('property', name);
            else m.setAttribute('name', name);
            m.setAttribute('content', content);
            head.appendChild(m);
        }}

        // ── Web App Manifest ──
        ensureLink('manifest', {{href: '{manifest_uri}'}});

        // ── iOS / iPadOS Safari ──
        {f"ensureLink('apple-touch-icon', {{href: '{icon_180}', sizes: '180x180'}});" if icon_180 else ""}
        {f"ensureLink('apple-touch-icon', {{href: '{icon_152}', sizes: '152x152'}});" if icon_152 else ""}
        {f"ensureLink('apple-touch-icon', {{href: '{icon_167}', sizes: '167x167'}});" if icon_167 else ""}
        ensureMeta('apple-mobile-web-app-capable', 'yes');
        ensureMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
        ensureMeta('apple-mobile-web-app-title', '{_BRAND_SHORT}');
        ensureMeta('mobile-web-app-capable', 'yes');

        // ── Android Chrome / 汎用 ──
        {f"ensureLink('icon', {{type: 'image/png', sizes: '192x192', href: '{icon_192}'}});" if icon_192 else ""}
        {f"ensureLink('icon', {{type: 'image/png', sizes: '512x512', href: '{icon_512}'}});" if icon_512 else ""}
        {f"ensureLink('icon', {{type: 'image/png', sizes: '32x32', href: '{icon_32}'}});" if icon_32 else ""}
        {f"ensureLink('icon', {{type: 'image/png', sizes: '16x16', href: '{icon_16}'}});" if icon_16 else ""}
        {f"ensureLink('shortcut icon', {{href: '{icon_32}'}});" if icon_32 else ""}

        // ── Windows / Edge ──
        {f"ensureMeta('msapplication-TileImage', '{icon_144}');" if icon_144 else ""}
        ensureMeta('msapplication-TileColor', '{_THEME_COLOR}');
        ensureMeta('msapplication-config', 'none');

        // ── Theme color ──
        ensureMeta('theme-color', '{_THEME_COLOR}');
        ensureMeta('color-scheme', 'dark light');

        // ── Viewport: safe-area-inset (iOS ノッチ/Dynamic Island 対応) ──
        (function() {{
            var vp = doc.querySelector('meta[name="viewport"]');
            if (vp) {{
                var content = vp.getAttribute('content') || '';
                if (!content.includes('viewport-fit')) {{
                    vp.setAttribute('content', content + ', viewport-fit=cover');
                }}
            }}
        }})();

        // ── iOS standalone モード: safe-area padding を body に適用 ──
        if (window.navigator.standalone || window.matchMedia('(display-mode: standalone)').matches) {{
            var style = doc.createElement('style');
            style.textContent = [
                ':root {{',
                '  --sat: env(safe-area-inset-top, 0px);',
                '  --sab: env(safe-area-inset-bottom, 0px);',
                '}}',
                '[data-testid="stAppViewContainer"] {{',
                '  padding-top: var(--sat) !important;',
                '  padding-bottom: var(--sab) !important;',
                '}}'
            ].join('\\n');
            head.appendChild(style);
        }}

        // ── OGP ──
        ensureMeta('og:title', '{_BRAND_NAME}', true);
        ensureMeta('og:description', '{_BRAND_DESC}', true);
        ensureMeta('og:type', 'website', true);
        {f"ensureMeta('og:image', '{icon_512}', true);" if icon_512 else ""}
        ensureMeta('twitter:card', 'summary');
        ensureMeta('twitter:title', '{_BRAND_NAME}');
        ensureMeta('twitter:description', '{_BRAND_DESC}');
        {f"ensureMeta('twitter:image', '{icon_512}');" if icon_512 else ""}
        ensureMeta('application-name', '{_BRAND_SHORT}');

        // ── オフライン検出バナー ──
        (function() {{
            var banner = doc.createElement('div');
            banner.id = 'mam-offline-banner';
            banner.style.cssText = [
                'display:none;position:fixed;top:0;left:0;right:0;z-index:99999;',
                'background:#dc2626;color:#fff;text-align:center;font-size:13px;',
                'padding:6px 12px;font-family:system-ui,sans-serif;'
            ].join('');
            banner.textContent = '⚠ オフラインです。一部機能が制限されます';
            doc.body.appendChild(banner);

            function updateBanner() {{
                banner.style.display = navigator.onLine ? 'none' : 'block';
            }}
            window.addEventListener('online',  updateBanner);
            window.addEventListener('offline', updateBanner);
            updateBanner();
        }})();

        // ── Android/Chrome PWA インストールプロンプト ──
        (function() {{
            if (window.matchMedia('(display-mode: standalone)').matches) return;
            if (localStorage.getItem('mam-pwa-dismissed')) return;

            var deferredPrompt = null;
            window.addEventListener('beforeinstallprompt', function(e) {{
                e.preventDefault();
                deferredPrompt = e;
                showInstallBanner();
            }});

            function showInstallBanner() {{
                var banner = doc.createElement('div');
                banner.id = 'mam-install-banner';
                banner.style.cssText = [
                    'position:fixed;bottom:16px;left:16px;right:16px;max-width:360px;margin:0 auto;',
                    'background:#1a1a1e;border:1px solid #333;border-radius:12px;',
                    'padding:12px 16px;display:flex;align-items:center;gap:12px;',
                    'z-index:99998;box-shadow:0 4px 20px rgba(0,0,0,.4);',
                    'font-family:system-ui,sans-serif;'
                ].join('');
                banner.innerHTML = [
                    '<div style="flex:1;min-width:0;">',
                    '  <div style="color:#fff;font-weight:600;font-size:13px;">アプリをインストール</div>',
                    '  <div style="color:#888;font-size:12px;margin-top:2px;">ホーム画面からすぐ起動</div>',
                    '</div>',
                    '<button id="mam-install-btn" style="',
                    '  padding:6px 14px;background:#2563eb;color:#fff;border:none;',
                    '  border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;">',
                    '  インストール</button>',
                    '<button id="mam-dismiss-btn" style="',
                    '  padding:4px;background:none;border:none;color:#666;cursor:pointer;font-size:18px;',
                    '  line-height:1;">×</button>',
                ].join('');
                doc.body.appendChild(banner);

                doc.getElementById('mam-install-btn').onclick = function() {{
                    if (deferredPrompt) {{
                        deferredPrompt.prompt();
                        deferredPrompt.userChoice.then(function() {{
                            banner.remove();
                            deferredPrompt = null;
                        }});
                    }}
                }};
                doc.getElementById('mam-dismiss-btn').onclick = function() {{
                    banner.remove();
                    localStorage.setItem('mam-pwa-dismissed', '1');
                }};
            }}
        }})();

    }} catch(e) {{
        console.warn('PWA injection failed:', e);
    }}
    </script>
    """

    # Streamlit の HTML コンポーネントとして 0px サイズで注入
    try:
        st.iframe(srcdoc=js, height=0, scrolling=False)   # type: ignore[attr-defined]
    except Exception:
        import streamlit.components.v1 as components
        components.html(js, height=0)
