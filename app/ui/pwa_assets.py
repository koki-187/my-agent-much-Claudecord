"""
PWA (Progressive Web App) アセット注入モジュール

Streamlit には標準で <head> 要素を追加する API がないため、
JavaScript で動的にメタタグ・リンク要素を <head> に挿入する。

対応OS / ブラウザ:
- iOS Safari (apple-touch-icon)
- Android Chrome (manifest, 192/512)
- Windows (msapplication-TileImage, browserconfig)
- macOS Safari (mask-icon, apple-touch-icon)
- Edge / Firefox / Chrome (manifest)
- ホーム画面に追加 (PWA install prompt)
"""
from __future__ import annotations
import base64
import json
import os
from typing import Optional

import streamlit as st


_LOGO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "mam_logo")
_BRAND_NAME = "My Agent Match"
_BRAND_SHORT = "MAM"
_BRAND_DESC = "不動産仲介プロ向け AI 案件調査・営業判断支援システム"
_THEME_COLOR = "#0A0A0C"        # サイドバー黒（クロームシルバーテーマ）
_BG_COLOR = "#0A0A0C"            # スプラッシュ背景


def _b64_png(size: int) -> Optional[str]:
    """指定サイズの mam_NxN.png を base64 data URI で返す"""
    p = os.path.join(_LOGO_DIR, f"mam_{size}x{size}.png")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        b = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b}"


def _build_manifest() -> str:
    """PWA Web App Manifest を JSON 文字列で生成 (data URI 用)"""
    icons = []
    for sz in [192, 256, 384, 512, 1024]:
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
        "orientation": "portrait-primary",
        "background_color": _BG_COLOR,
        "theme_color": _THEME_COLOR,
        "lang": "ja",
        "categories": ["business", "productivity", "finance"],
        "icons": icons,
    }
    return json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))


def inject_pwa_head() -> None:
    """
    PWA 必須メタタグ・アイコンリンク・manifest を <head> に注入する。

    Streamlit のセキュリティ制約上、直接 <head> に挿入できないため、
    JavaScript で動的に <head> 配下に要素を追加する。
    """
    manifest_json = _build_manifest()
    manifest_uri = "data:application/manifest+json;charset=utf-8;base64," + \
                   base64.b64encode(manifest_json.encode()).decode()

    icon_180 = _b64_png(180) or _b64_png(192) or _b64_png(256)
    icon_192 = _b64_png(192)
    icon_512 = _b64_png(512)
    icon_32 = _b64_png(32)
    icon_16 = _b64_png(16)
    icon_152 = _b64_png(152)
    icon_167 = _b64_png(167)
    icon_144 = _b64_png(144)

    # JS で <head> に要素を追加
    # （Streamlit が <iframe> 内でも親 document を捕まえられるよう parent.document を使う）
    js = f"""
    <script>
    (function(){{
        try {{
            var doc = window.parent.document;
            var head = doc.head;

            function ensureLink(rel, attrs) {{
                // 同じ rel + sizes の既存要素を削除して上書き
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

            // ── Web App Manifest (PWA インストール対応)
            ensureLink('manifest', {{href: '{manifest_uri}'}});

            // ── iOS / iPadOS Safari
            {f"ensureLink('apple-touch-icon', {{href: '{icon_180}', sizes: '180x180'}});" if icon_180 else ""}
            {f"ensureLink('apple-touch-icon', {{href: '{icon_152}', sizes: '152x152'}});" if icon_152 else ""}
            {f"ensureLink('apple-touch-icon', {{href: '{icon_167}', sizes: '167x167'}});" if icon_167 else ""}
            ensureMeta('apple-mobile-web-app-capable', 'yes');
            ensureMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
            ensureMeta('apple-mobile-web-app-title', '{_BRAND_SHORT}');
            ensureMeta('mobile-web-app-capable', 'yes');

            // ── Android Chrome / 汎用
            {f"ensureLink('icon', {{type: 'image/png', sizes: '192x192', href: '{icon_192}'}});" if icon_192 else ""}
            {f"ensureLink('icon', {{type: 'image/png', sizes: '512x512', href: '{icon_512}'}});" if icon_512 else ""}
            {f"ensureLink('icon', {{type: 'image/png', sizes: '32x32', href: '{icon_32}'}});" if icon_32 else ""}
            {f"ensureLink('icon', {{type: 'image/png', sizes: '16x16', href: '{icon_16}'}});" if icon_16 else ""}
            {f"ensureLink('shortcut icon', {{href: '{icon_32}'}});" if icon_32 else ""}

            // ── Windows / Edge (msapplication)
            {f"ensureMeta('msapplication-TileImage', '{icon_144}');" if icon_144 else ""}
            ensureMeta('msapplication-TileColor', '{_THEME_COLOR}');
            ensureMeta('msapplication-config', 'none');

            // ── Theme color (Chrome address bar / Android nav)
            ensureMeta('theme-color', '{_THEME_COLOR}');
            ensureMeta('color-scheme', 'dark light');

            // ── OGP (社内シェア時のプレビュー用)
            ensureMeta('og:title', '{_BRAND_NAME}', true);
            ensureMeta('og:description', '{_BRAND_DESC}', true);
            ensureMeta('og:type', 'website', true);
            {f"ensureMeta('og:image', '{icon_512}', true);" if icon_512 else ""}
            ensureMeta('twitter:card', 'summary');
            ensureMeta('twitter:title', '{_BRAND_NAME}');
            ensureMeta('twitter:description', '{_BRAND_DESC}');
            {f"ensureMeta('twitter:image', '{icon_512}');" if icon_512 else ""}

            // ── Application name
            ensureMeta('application-name', '{_BRAND_SHORT}');

        }} catch(e) {{
            console.warn('PWA injection failed:', e);
        }}
    }})();
    </script>
    """
    # Streamlit の HTML コンポーネントとして 0px サイズで注入
    import streamlit.components.v1 as components
    components.html(js, height=0)
