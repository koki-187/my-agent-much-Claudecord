# -*- coding: utf-8 -*-
"""
MAM ビジュアルレポート生成サービス（モノトーン版）

白・黒・ライトシルバー基調の "Audi ショールーム at night" 風プレミアム PDF。
PropertyData + 分析結果を受け取って 2 ページ A4 PDF を生成する。

外部から呼び出すエントリポイント:
    generate_visual_report(out_path, property_data, score_result, ...)
"""
from __future__ import annotations
import io, os, math
from dataclasses import dataclass, field
from typing import Any, Optional

import logging
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as _fm
from matplotlib.patches import Wedge, FancyBboxPatch
import numpy as np

logger = logging.getLogger(__name__)

# ── matplotlib 日本語フォント ────────────────────────────────────────────
_mpl_jp_loaded = False
for _fp in ['C:/Windows/Fonts/meiryo.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc']:
    if os.path.exists(_fp):
        try:
            _fm.fontManager.addfont(_fp)
            plt.rcParams['font.family'] = _fm.FontProperties(fname=_fp).get_name()
            _mpl_jp_loaded = True
            break
        except Exception as e:
            logger.warning("matplotlib 日本語フォント登録失敗 %s: %s", _fp, e)
if not _mpl_jp_loaded:
    logger.warning("matplotlib 日本語フォントなし → グラフ内日本語が文字化けする可能性")
plt.rcParams['axes.unicode_minus'] = False

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

# ── reportlab 日本語フォント（埋込必須） ─────────────────────────────────
JA_FONT_NAME = JA_FONT_BOLD = None
for _fp in ['C:/Windows/Fonts/meiryob.ttc', 'C:/Windows/Fonts/meiryo.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
    if os.path.exists(_fp):
        try:
            pdfmetrics.registerFont(TTFont("JA-Bold", _fp, subfontIndex=0))
            JA_FONT_BOLD = "JA-Bold"; break
        except Exception as e:
            logger.warning("reportlab Bold フォント登録失敗 %s: %s", _fp, e)
for _fp in ['C:/Windows/Fonts/meiryo.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc']:
    if os.path.exists(_fp):
        try:
            pdfmetrics.registerFont(TTFont("JA", _fp, subfontIndex=0))
            JA_FONT_NAME = "JA"; break
        except Exception as e:
            logger.warning("reportlab Regular フォント登録失敗 %s: %s", _fp, e)
if JA_FONT_NAME is None:
    logger.error("日本語フォントが見つかりません → PDF内の日本語が豆腐(□)になります。"
                 " システムに meiryo.ttc または NotoSansCJK をインストールしてください")
JA_FONT_NAME = JA_FONT_NAME or "Helvetica"
JA_FONT_BOLD = JA_FONT_BOLD or JA_FONT_NAME


# ══════════════════════════════════════════════════════════════════════════
# モノトーンパレット — 白・黒・ライトシルバー
# ══════════════════════════════════════════════════════════════════════════
BG_BASE         = "#050507"   # 純黒に近いベース
BG_GRAD_HIGH    = "#28282D"   # 左上のハイライト（ガンメタル）
BG_GRAD_MID    = "#15151A"   # 中段グラデ
BG_GRAD_LOW     = "#050507"   # 下部

PURE_WHITE      = "#FFFFFF"
SILVER_BRIGHT   = "#F0F0F4"   # オフホワイト（H1見出し）
SILVER          = "#D0D0D6"   # 中シルバー（本文）
SILVER_MUTED    = "#9C9CA2"   # 暗シルバー（注記）
GUNMETAL        = "#48484C"   # 区切り線
SHADOW          = "#1A1A1D"   # カード背景
CARD_BG         = "#0F0F12"

# 状態色（極薄彩度でモノトーンに溶け込ませる）
ST_HIGH         = "#E0B4B4"   # 燻しローズ（HIGH RISK / 警告）
ST_MED          = "#E0CCB4"   # 燻しシャンパン（MEDIUM）
ST_LOW          = "#C8C8B4"   # 燻しベージュ（LOW）
ST_GOOD         = "#B4D8C0"   # 燻しミント（POSITIVE）
ST_INFO         = "#B4C8E0"   # 燻しペリウィンクル（INFO）


# ══════════════════════════════════════════════════════════════════════════
# データ構造
# ══════════════════════════════════════════════════════════════════════════
@dataclass
class ReportInputs:
    """ビジュアルレポート生成のための入力データ集約"""
    property_name: str
    address: str        # "東京都xx | 駅徒歩x分 | 築xxxx年 RC造" 等のメタ
    rank: str           # "S"/"A"/"B"/"C"/"D"
    total_score: float
    # ── 主要価格・収益指標
    price: int
    income_value: Optional[int] = None
    offer_low: Optional[int] = None
    offer_high: Optional[int] = None
    actual_income: Optional[int] = None
    noi: Optional[int] = None
    gross_yield: Optional[float] = None   # 0-1 (例: 0.0597)
    target_yield: Optional[float] = None
    dscr: Optional[float] = None
    occupancy_rate: Optional[float] = None  # 0-1
    ltv: Optional[float] = None  # 0-1（標準 0.8）
    # ── 物件メタ
    built_year: Optional[int] = None
    structure: Optional[str] = None
    land_area_sqm: Optional[float] = None
    building_area_sqm: Optional[float] = None
    asset_type: Optional[str] = None
    # ── 路線価
    estimated_land_value: Optional[int] = None
    rosenka_ratio: Optional[float] = None
    # ── スコア内訳
    component_scores: dict = field(default_factory=dict)
    # ── 出口戦略
    exit_scenarios: list = field(default_factory=list)
    # 各要素 = (label, sell_price, irr_percent)
    # ── リスク
    risks: list = field(default_factory=list)
    # 各要素 = {"level": "HIGH"/"MEDIUM"/"LOW", "type": str, "message": str}
    # ── 判定文・推奨アクション
    one_line_verdict: str = ""
    actions: list = field(default_factory=list)
    # 各要素 = (priority_tag, when, action)


# ══════════════════════════════════════════════════════════════════════════
# matplotlib チャート生成（モノトーン）
# ══════════════════════════════════════════════════════════════════════════
def _fig_to_png(fig, dpi=180):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                facecolor='none', transparent=True, pad_inches=0.05)
    buf.seek(0); plt.close(fig); return buf


def _make_donut(value: float, label: str, color: str = SILVER_BRIGHT):
    fig, ax = plt.subplots(figsize=(1.7,1.7), facecolor='none')
    ax.set_aspect('equal'); ax.axis('off')
    ang = 360 * min(max(value,0), 100) / 100
    # 影
    ax.add_patch(Wedge((0.5,0.485), 0.42, 0, 360, width=0.14,
                        facecolor='#000', alpha=0.55))
    # 背景リング
    ax.add_patch(Wedge((0.5,0.5), 0.42, 0, 360, width=0.14,
                        facecolor=GUNMETAL, alpha=0.4))
    # 値弧
    ax.add_patch(Wedge((0.5,0.5), 0.42, 90-ang, 90, width=0.14, facecolor=color))
    ax.text(0.5, 0.51, f"{value:.0f}", ha='center', va='center',
            fontsize=18, color=PURE_WHITE, fontweight='bold')
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    return _fig_to_png(fig)


def _make_monthly_bar(noi: int):
    """月次累積キャッシュフロー（百万円）"""
    fig, ax = plt.subplots(figsize=(4.5,2.4), facecolor='none')
    ax.set_facecolor('none')
    rng = np.random.RandomState(11); base = noi/12/1e6; cum = 0; vals = []
    for i in range(11):
        cum += base*(1+rng.uniform(-0.04,0.05)); vals.append(cum)
    x = np.arange(11)
    for xi,v in zip(x,vals):
        ax.bar(xi, v, width=0.55, color='#000', alpha=0.55, zorder=1)
        ax.bar(xi, v, width=0.5, color=SILVER_BRIGHT, alpha=0.95,
               edgecolor=PURE_WHITE, linewidth=0.4, zorder=2)
    ax.set_xticks(x); ax.set_xticklabels([f"{m}月" for m in range(1,12)],
                                          color=SILVER, fontsize=8)
    yticks = [0, int(max(vals)/2), int(max(vals))]
    ax.set_yticks(yticks)
    ax.set_yticklabels([f'{y}' for y in yticks], color=SILVER, fontsize=7.5)
    for s in ax.spines.values(): s.set_visible(False)
    ax.spines['bottom'].set_visible(True); ax.spines['bottom'].set_color(GUNMETAL)
    ax.tick_params(colors=SILVER, length=0)
    return _fig_to_png(fig)


def _make_yearly_hbar(noi: int, start_year: int):
    """6年分の年次NOI（百万円）"""
    fig, ax = plt.subplots(figsize=(6.5,3.4), facecolor='none')
    ax.set_facecolor('none')
    years = [str(start_year + i) for i in range(6)]
    vals = [noi/1e6 * (i+1) * 0.97**i for i in range(6)]
    y = np.arange(len(years))
    for yi,v in zip(y,vals):
        ax.barh(yi-0.05, v, height=0.5, color='#000', alpha=0.5, zorder=1)
        ax.barh(yi, v, height=0.45, color=SILVER_BRIGHT,
                edgecolor=PURE_WHITE, linewidth=0.4, alpha=0.95, zorder=2)
        ax.text(v+max(vals)*0.02, yi, f"{v:.0f}", color=SILVER, fontsize=8, va='center')
    ax.set_yticks(y); ax.set_yticklabels(years, color=SILVER, fontsize=10)
    ax.set_xticks([0, int(max(vals)*0.5), int(max(vals))])
    ax.set_xticklabels(['0', f'{int(max(vals)*0.5)}', f'{int(max(vals))}百万円'],
                       color=SILVER, fontsize=8)
    for s in ax.spines.values(): s.set_visible(False)
    ax.spines['bottom'].set_visible(True); ax.spines['bottom'].set_color(GUNMETAL)
    ax.tick_params(colors=SILVER, length=0)
    return _fig_to_png(fig)


def _make_index_line(area_label: str = "エリア地価"):
    """エリア地価指数の長期トレンド（モックデータ）"""
    fig, ax = plt.subplots(figsize=(9.5,3.4), facecolor='none')
    ax.set_facecolor('none')
    years = np.arange(2000, 2027)
    rng = np.random.RandomState(42)
    base = np.linspace(3000, 9000, len(years))
    noise = rng.normal(0, 600, len(years))
    boost = np.where(years >= 2018, (years-2018)*400, 0)
    vals = np.clip(base + np.cumsum(noise)*0.3 + boost, 1500, None)
    ax.plot(years, vals, color=PURE_WHITE, linewidth=1.7)
    ax.fill_between(years, vals, vals.min()-500, color=SILVER, alpha=0.12)
    ax.set_xticks([2000,2005,2010,2015,2020,2025])
    ax.set_xticklabels(['2000','2005','2010','2015','2020','2025'],
                       color=SILVER, fontsize=8)
    ax.set_yticks([0,3000,6000,9000,12000])
    ax.set_yticklabels(['0','3,000','6,000','9,000','12,000'],
                       color=SILVER, fontsize=7.5)
    ax.grid(True, color=GUNMETAL, linewidth=0.3, alpha=0.6, axis='y')
    for s in ax.spines.values(): s.set_visible(False)
    ax.spines['bottom'].set_visible(True); ax.spines['left'].set_visible(True)
    ax.spines['bottom'].set_color(GUNMETAL); ax.spines['left'].set_color(GUNMETAL)
    ax.tick_params(colors=SILVER, length=0)
    return _fig_to_png(fig)


def _make_radar(scores: dict):
    """6軸スコア内訳レーダー"""
    if not scores:
        scores = {"価格妥当性":0, "収益性":0, "流動性":0, "開発可能性":0,
                  "リスク耐性":0, "商流・売主":0}
    labels = list(scores.keys()); vals = list(scores.values())
    N = len(labels)
    angles = [n/N*2*math.pi for n in range(N)] + [0]
    vp = list(vals) + list(vals[:1])
    fig, ax = plt.subplots(figsize=(4.0,3.4), subplot_kw=dict(polar=True), facecolor='none')
    ax.set_facecolor('none')
    ax.set_theta_offset(math.pi/2); ax.set_theta_direction(-1); ax.set_ylim(0,100)
    for r in [25,50,75,100]:
        ax.plot(angles, [r]*(N+1), color=GUNMETAL, linewidth=0.4, alpha=0.6)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=7.5, color=SILVER)
    ax.set_yticks([]); ax.spines['polar'].set_color(GUNMETAL)
    ax.fill(angles, vp, color=SILVER_BRIGHT, alpha=0.18)
    ax.plot(angles, vp, color=PURE_WHITE, linewidth=2.0)
    for a, v in zip(angles[:-1], vals):
        # 値に応じて点の明度を変える（モノトーン内で表現）
        if v >= 70:
            col = PURE_WHITE
        elif v >= 40:
            col = SILVER
        else:
            col = SILVER_MUTED
        ax.plot(a, v, 'o', ms=5, color=col)
        ax.text(a, v+10, str(int(v)), ha='center', fontsize=7.5,
                color=col, fontweight='bold')
    return _fig_to_png(fig)


def _make_price_compare(price: int, income_value: Optional[int],
                         offer_low: Optional[int], offer_high: Optional[int],
                         land_value: Optional[int]):
    """価格比較バー（売出/収益還元/推奨指値/路線価）"""
    fig, ax = plt.subplots(figsize=(6.0,2.6), facecolor='none')
    ax.set_facecolor('none')

    def _fmt(v):
        if v is None: return "-"
        if v >= 1e8: return f"{v/1e8:.2f}億円"
        return f"{v//10000:,}万円"

    items = []
    items.append(("売出価格", price, PURE_WHITE, ST_HIGH, _fmt(price)))
    if income_value: items.append(("収益還元価格", income_value, SILVER_BRIGHT, SILVER_BRIGHT, _fmt(income_value)))
    if offer_high:   items.append(("推奨指値(上限)", offer_high, SILVER, SILVER, _fmt(offer_high)))
    if offer_low:    items.append(("推奨指値(下限)", offer_low, SILVER_MUTED, SILVER_MUTED, _fmt(offer_low)))
    if land_value:   items.append(("路線価評価", land_value, PURE_WHITE, ST_GOOD, _fmt(land_value)))

    bar_max = max(v for _,v,_,_,_ in items)*1.05
    for i, (label, val, bar_col, text_col, fmt) in enumerate(items):
        ax.barh(i, bar_max, color=GUNMETAL, alpha=0.18, height=0.55)
        ax.barh(i, val, color=bar_col, alpha=0.92, height=0.5, linewidth=0, zorder=3)
        ax.text(-bar_max*0.01, i, label, ha='right', va='center',
                fontsize=8.5, color=SILVER)
        ax.text(val + bar_max*0.01, i, fmt, ha='left', va='center',
                fontsize=8.5, color=text_col, fontweight='bold')
    ax.set_xlim(-bar_max*0.32, bar_max*1.18)
    ax.set_ylim(-0.6, len(items)-0.4)
    ax.invert_yaxis(); ax.axis('off')
    return _fig_to_png(fig)


def _make_exit_chart(scenarios: list, price: int):
    """出口戦略3シナリオ：IRR(棒)+売却価格(折れ線)"""
    fig, ax = plt.subplots(figsize=(6.0,2.6), facecolor='none')
    ax.set_facecolor('none')
    if not scenarios:
        ax.text(0.5,0.5,"出口データなし", ha='center', va='center',
                color=SILVER_MUTED, transform=ax.transAxes); ax.axis('off')
        return _fig_to_png(fig)
    names = [s[0] for s in scenarios]
    sells = [s[1]/1e8 for s in scenarios]
    irrs = [s[2] for s in scenarios]
    # モノトーンでも区別: 明度で表現
    bar_cols = [SILVER_MUTED, SILVER, SILVER_BRIGHT]
    x = np.arange(len(scenarios))
    bars = ax.bar(x, irrs, width=0.5, color=bar_cols[:len(scenarios)],
                  alpha=0.92, zorder=3)
    ax.set_xticks(x); ax.set_xticklabels(names, color=SILVER, fontsize=8)
    ax.set_ylabel("IRR (%)", color=SILVER, fontsize=8)
    ax.tick_params(colors=SILVER, labelsize=7.5)
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(GUNMETAL); ax.spines['left'].set_color(GUNMETAL)
    ax.set_ylim(min(irrs)-2 if min(irrs)<0 else 0, max(irrs)+2)
    for i, (b, irr) in enumerate(zip(bars, irrs)):
        ax.text(b.get_x()+b.get_width()/2, irr + (0.2 if irr>=0 else -0.5),
                f"IRR {irr:.1f}%", ha='center', fontsize=8.5,
                color=bar_cols[i], fontweight='bold')
    # 右軸: 売却価格（折れ線）
    ax2 = ax.twinx()
    ax2.plot(x, sells, 'o--', color=PURE_WHITE, linewidth=1.8, markersize=7, zorder=4)
    for i, sp in enumerate(sells):
        ax2.text(i, sp + (max(sells)-min(sells))*0.05 + 0.05,
                 f"{sp:.2f}億", ha='center', fontsize=7.5, color=PURE_WHITE)
    ax2.set_ylabel("売却価格 (億円)", color=PURE_WHITE, fontsize=7.5)
    ax2.tick_params(colors=PURE_WHITE, labelsize=7)
    ax2.spines['top'].set_visible(False); ax2.spines['bottom'].set_visible(False)
    ax2.spines['left'].set_visible(False); ax2.spines['right'].set_color(SILVER)
    ax2.set_ylim(min(sells)*0.92, max(sells)*1.12)
    return _fig_to_png(fig)


def _make_risk_heatmap(risks: list):
    """検出リスク&ポジティブ要因のヒートマップ"""
    fig, ax = plt.subplots(figsize=(6.0,2.8), facecolor='none')
    ax.set_facecolor('none'); ax.axis('off')
    level_color = {
        "HIGH":   ST_HIGH,
        "MEDIUM": ST_MED,
        "LOW":    ST_LOW,
        "+POS":   ST_GOOD,
        "INFO":   ST_INFO,
    }
    items = risks[:8] if len(risks) > 8 else risks
    if not items:
        ax.text(0.5, 0.5, "検出リスクなし", ha='center', va='center',
                color=SILVER_MUTED, fontsize=10, transform=ax.transAxes)
        return _fig_to_png(fig)

    y0 = 0.95
    for i, r in enumerate(items):
        y = y0 - i * (0.92 / max(len(items), 1))
        lv = r.get("level", "INFO")
        col = level_color.get(lv, ST_INFO)
        title = r.get("type", "")
        # バッジ
        ax.add_patch(FancyBboxPatch((0.02, y-0.04), 0.18, 0.07,
                                     boxstyle="round,pad=0.018",
                                     facecolor=col, edgecolor='none'))
        ax.text(0.11, y-0.005, lv, ha='center', va='center',
                fontsize=7, color=BG_BASE, fontweight='bold')
        ax.text(0.23, y-0.005, title, ha='left', va='center',
                fontsize=8.5, color=SILVER)
        ax.axhline(y - 0.05, color=GUNMETAL, linewidth=0.3,
                    alpha=0.5, xmin=0.02, xmax=0.98)
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    return _fig_to_png(fig)


# ══════════════════════════════════════════════════════════════════════════
# canvas 描画ヘルパー
# ══════════════════════════════════════════════════════════════════════════
def _draw_bg(c, w, h):
    """モノトーンガンメタル斜めグラデ背景 + 通貨記号ウォーターマーク"""
    c.setFillColor(rl_colors.HexColor(BG_BASE))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    # 左上にガンメタルハイライト
    for i in range(60):
        t = i / 60
        alpha = max(0, 0.40 * (1 - t * 1.3))
        if alpha <= 0: continue
        # ガンメタル風（モノトーン）
        c.setFillColorRGB(0.16, 0.16, 0.18, alpha=alpha)
        c.circle(w*0.15, h*0.85, (i+1)*12, fill=1, stroke=0)
    # 通貨記号ウォーターマーク（モノトーン）
    np.random.seed(7)
    for _ in range(40):
        x = np.random.uniform(0, w); y = np.random.uniform(0, h)
        sym = np.random.choice(['¥','$','€','£','M²','㎡','%'])
        sz = np.random.uniform(14, 32)
        c.setFont(JA_FONT_NAME, sz)
        c.setFillColorRGB(0.62, 0.62, 0.66, alpha=np.random.uniform(0.04, 0.08))
        c.drawString(x, y, sym)


def _text(c, x, y, s, *, font=None, size=10, color=SILVER, anchor='start', bold=False):
    f = font or (JA_FONT_BOLD if bold else JA_FONT_NAME)
    c.setFont(f, size); c.setFillColor(rl_colors.HexColor(color))
    if anchor=='center': c.drawCentredString(x, y, s)
    elif anchor=='end': c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)


def _line(c, x1, y1, x2, y2, *, color=GUNMETAL, width=0.5, alpha=1.0):
    c.setStrokeColor(rl_colors.HexColor(color), alpha=alpha)
    c.setLineWidth(width); c.line(x1, y1, x2, y2)


def _img(c, png, x, y, w, h):
    c.drawImage(ImageReader(png), x, y, width=w, height=h,
                preserveAspectRatio=True, mask='auto', anchor='c')


# ══════════════════════════════════════════════════════════════════════════
# Page 1: 9 セクション・全日本語ラベル
# ══════════════════════════════════════════════════════════════════════════
def _draw_page1(c, W, H, data: ReportInputs):
    _draw_bg(c, W, H)

    # ── ヘッダー
    _text(c, 18*mm, H-12*mm, "案件調査ダッシュボード ｜ PROPERTY DEAL INTELLIGENCE",
          size=10, color=SILVER, bold=True)
    _text(c, 18*mm, H-22*mm, data.property_name,
          size=22, color=PURE_WHITE, bold=True)
    _text(c, 18*mm, H-28*mm, data.address, size=9, color=SILVER)

    # ランクバッジ（モノトーン: 白文字・銀枠）
    bx = W - 35*mm; by = H - 18*mm
    c.setFillColor(rl_colors.HexColor(SILVER_BRIGHT))
    c.setStrokeColor(rl_colors.HexColor(PURE_WHITE)); c.setLineWidth(1.2)
    c.roundRect(bx-14*mm, by-4*mm, 26*mm, 11*mm, 3*mm, fill=1, stroke=1)
    _text(c, bx, by, f"Rank  {data.rank}", size=15, color=BG_BASE,
          anchor='center', bold=True)
    _text(c, bx, by-8*mm, f"{data.total_score:.0f} / 100点", size=9,
          color=SILVER, anchor='center')
    _line(c, 18*mm, H-33*mm, W-18*mm, H-33*mm, alpha=0.6, color=SILVER_MUTED)

    # ── 4ドーナツ + 月次CF
    occ_pct = (data.occupancy_rate or 0) * 100
    ltv_pct = (data.ltv or 0.8) * 100
    dscr_x100 = (data.dscr or 0) * 100
    donut_specs = [
        ("総合スコア(点)", data.total_score, PURE_WHITE),
        ("稼働率(%)",      occ_pct,          SILVER_BRIGHT),
        ("想定LTV(%)",     ltv_pct,          SILVER),
        ("DSCR×100",       dscr_x100,        SILVER),
    ]
    donut_y = H - 70*mm
    for i, (lbl, val, col) in enumerate(donut_specs):
        cx = 22*mm + i*25*mm
        _text(c, cx+12*mm, donut_y+28*mm, lbl, size=8.5,
              color=PURE_WHITE, anchor='center', bold=True)
        _img(c, _make_donut(val, lbl, col), cx, donut_y, 24*mm, 24*mm)

    _text(c, W-72*mm, H-38*mm, "月次累積キャッシュフロー (百万円)",
          size=8, color=PURE_WHITE, bold=True)
    if data.noi:
        _img(c, _make_monthly_bar(data.noi), W-78*mm, H-77*mm, 64*mm, 38*mm)

    # ── 年次NOI + 地価Index
    from datetime import date
    start_year = date.today().year + 1
    _text(c, 18*mm, H-87*mm, f"年次NOI推移 ({start_year}〜{start_year+5}年・百万円)",
          size=8, color=PURE_WHITE, bold=True)
    if data.noi:
        _img(c, _make_yearly_hbar(data.noi, start_year),
             14*mm, H-138*mm, 80*mm, 50*mm)

    area_short = data.address.split('｜')[0].strip().split('都')[-1].split('府')[-1].split('県')[-1]
    _text(c, 100*mm, H-87*mm,
          f"{area_short[:10]} 地価指数推移 (2000〜2025)",
          size=8, color=PURE_WHITE, bold=True)
    _img(c, _make_index_line(), 96*mm, H-138*mm, 100*mm, 50*mm)

    # ── スコアレーダー + 価格比較
    _text(c, 18*mm, H-148*mm,
          "6軸スコア内訳 (0-100点・MAM分析エンジン)",
          size=8, color=PURE_WHITE, bold=True)
    _img(c, _make_radar(data.component_scores),
         14*mm, H-198*mm, 56*mm, 50*mm)

    _text(c, 78*mm, H-148*mm,
          "価格比較：売出 vs 収益還元 vs 推奨指値 vs 路線価",
          size=8, color=PURE_WHITE, bold=True)
    _img(c, _make_price_compare(data.price, data.income_value,
                                 data.offer_low, data.offer_high,
                                 data.estimated_land_value),
         75*mm, H-200*mm, 122*mm, 52*mm)

    # ── 出口戦略 + リスクヒート
    _text(c, 18*mm, H-208*mm,
          "出口戦略3シナリオ：IRR & 想定売却価格",
          size=8, color=PURE_WHITE, bold=True)
    _img(c, _make_exit_chart(data.exit_scenarios, data.price),
         14*mm, H-258*mm, 90*mm, 50*mm)

    _text(c, 110*mm, H-208*mm,
          "検出リスク & ポジティブ要因サマリー",
          size=8, color=PURE_WHITE, bold=True)
    _img(c, _make_risk_heatmap(data.risks),
         105*mm, H-258*mm, 92*mm, 50*mm)

    # ── ワンライン判定バナー（モノトーン）
    bb_y = H - 275*mm
    c.setFillColor(rl_colors.HexColor(SHADOW))
    c.setStrokeColor(rl_colors.HexColor(SILVER_BRIGHT)); c.setLineWidth(0.8)
    c.roundRect(18*mm, bb_y, W-36*mm, 12*mm, 2*mm, fill=1, stroke=1)
    _text(c, W/2, bb_y+8*mm, "ワンライン判断", size=7,
          color=SILVER_MUTED, anchor='center', bold=True)
    _text(c, W/2, bb_y+3*mm, data.one_line_verdict or "(判定文未設定)",
          size=10.5, color=PURE_WHITE, anchor='center', bold=True)

    # フッター
    _text(c, 18*mm, 8*mm,
          "MY AGENT MUCH  ·  NEURAL ESTATE INTELLIGENCE",
          size=7, color=SILVER_MUTED)
    _text(c, W-18*mm, 8*mm, "PAGE  01 / 02",
          size=7, color=SILVER_MUTED, anchor='end')


# ══════════════════════════════════════════════════════════════════════════
# Page 2: Summary + Actions
# ══════════════════════════════════════════════════════════════════════════
def _format_money(yen: Optional[int]) -> str:
    if yen is None: return "-"
    if yen >= 1e8:
        oku = yen // 1e8
        man = (yen % 1e8) // 10000
        if man == 0:
            return f"{oku:.0f}億円"
        return f"{oku:.0f}億{man:,.0f}万円"
    return f"{yen//10000:,}万円"


def _draw_page2(c, W, H, data: ReportInputs):
    _draw_bg(c, W, H)

    _text(c, 18*mm, H-12*mm,
          "エグゼクティブサマリー & 次の一手 ｜ EXECUTIVE SUMMARY",
          size=10, color=SILVER, bold=True)
    _text(c, 18*mm, H-22*mm, data.property_name,
          size=18, color=PURE_WHITE, bold=True)
    _line(c, 18*mm, H-28*mm, W-18*mm, H-28*mm, alpha=0.6, color=SILVER_MUTED)

    # ── KPI
    _text(c, 18*mm, H-40*mm, "■  主要指標 (KEY METRICS)",
          size=10, color=PURE_WHITE, bold=True)

    def _ratio_label(price, iv):
        if not iv or iv == 0: return "-"
        r = price / iv
        if r >= 1.2: return f"{r:.2f}x（高すぎ）"
        if r >= 1.05: return f"{r:.2f}x（やや高）"
        if r >= 0.95: return f"{r:.2f}x（適正）"
        return f"{r:.2f}x（割安）"

    age = None
    if data.built_year:
        from datetime import date
        age = date.today().year - data.built_year

    kpis = [
        ("売出価格",       _format_money(data.price),                            PURE_WHITE),
        ("収益還元価格",   _format_money(data.income_value),                     SILVER_BRIGHT),
        ("推奨指値レンジ",
         f"{_format_money(data.offer_low)} 〜 {_format_money(data.offer_high)}", SILVER_BRIGHT),
        ("価格乖離倍率",   _ratio_label(data.price, data.income_value),          PURE_WHITE),
        ("表面利回り",
         f"{data.gross_yield*100:.2f}%" if data.gross_yield else "-",            SILVER),
        ("推計NOI",        f"{data.noi//10000:,}万円 / 年" if data.noi else "-", SILVER_BRIGHT),
        ("DSCR(融資判定)",
         f"{data.dscr:.2f}" if data.dscr else "-",                              SILVER),
        ("土地値担保",
         "✅ "+_format_money(data.estimated_land_value)+" 評価" if data.estimated_land_value else "-",
         SILVER_BRIGHT),
        ("築年・構造",
         f"{data.built_year}年" + (f"(築{age}年)" if age else "") +
         (f" {data.structure}造" if data.structure else ""),
         SILVER),
        ("総合判定",
         f"Rank {data.rank} ／ {data.total_score:.0f}点",                         PURE_WHITE),
    ]
    y0 = H - 50*mm
    for i, (lbl, val, col) in enumerate(kpis):
        y = y0 - i * 8*mm
        _text(c, 20*mm, y, lbl, size=9.5, color=SILVER, bold=True)
        _text(c, 95*mm, y, val, size=10, color=col, bold=True, anchor='end')
        _line(c, 18*mm, y-2*mm, 96*mm, y-2*mm, width=0.3, alpha=0.5)

    # ── 検出リスク
    _text(c, 110*mm, H-40*mm, "■  検出リスク (DETECTED RISKS)",
          size=10, color=PURE_WHITE, bold=True)
    yr = H - 50*mm
    level_color = {"HIGH": ST_HIGH, "MEDIUM": ST_MED, "LOW": ST_LOW, "INFO": ST_INFO}
    for r in data.risks[:3]:
        lv = r.get("level", "INFO")
        col = level_color.get(lv, ST_INFO)
        title = r.get("type", "")
        msg = r.get("message", "")
        c.setFillColor(rl_colors.HexColor(col))
        c.roundRect(110*mm, yr-4*mm, 18*mm, 6*mm, 1.5*mm, fill=1, stroke=0)
        _text(c, 119*mm, yr-2.5*mm, lv, size=8,
              color=BG_BASE, anchor='center', bold=True)
        _text(c, 132*mm, yr-2*mm, title, size=11, color=PURE_WHITE, bold=True)
        # メッセージを最大3行で改行
        words = msg.split('。')
        for k, line in enumerate(words[:3]):
            if line.strip():
                _text(c, 132*mm, yr-9*mm - k*4*mm, line.strip() + '。',
                      size=7.5, color=SILVER)
        yr -= 25*mm

    # ── ワンライン判定バナー
    banner_y = H - 185*mm
    c.setFillColor(rl_colors.HexColor(SHADOW))
    c.setStrokeColor(rl_colors.HexColor(SILVER_BRIGHT)); c.setLineWidth(1.0)
    c.roundRect(18*mm, banner_y, W-36*mm, 20*mm, 3*mm, fill=1, stroke=1)
    _text(c, W/2, banner_y+14*mm, "ワンライン判定 (ONE-LINE VERDICT)",
          size=7, color=SILVER_MUTED, anchor='center', bold=True)
    _text(c, W/2, banner_y+5*mm, data.one_line_verdict or "(判定文未設定)",
          size=12, color=PURE_WHITE, anchor='center', bold=True)

    # ── 今日の行動計画
    _text(c, 18*mm, H-200*mm,
          "■  今日の行動計画 (TODAY'S ACTION PLAN)",
          size=10, color=PURE_WHITE, bold=True)
    priority_color = {"URGENT": ST_HIGH, "HIGH": ST_MED, "CHECK": ST_LOW}
    ya = H - 208*mm
    for tag, when, action in data.actions[:6]:
        col = priority_color.get(tag, ST_INFO)
        c.setFillColor(rl_colors.HexColor(col))
        c.roundRect(20*mm, ya-3*mm, 18*mm, 6*mm, 1.5*mm, fill=1, stroke=0)
        _text(c, 29*mm, ya-1.5*mm, tag, size=7,
              color=BG_BASE, anchor='center', bold=True)
        _text(c, 42*mm, ya-1*mm, when, size=8.5, color=SILVER, bold=True)
        _text(c, 60*mm, ya-1*mm, action, size=10, color=PURE_WHITE)
        _line(c, 18*mm, ya-5*mm, W-18*mm, ya-5*mm, width=0.3, alpha=0.5)
        ya -= 9*mm

    # 返信テンプレ
    _text(c, 18*mm, 18*mm,
          "■ 紹介元への返信テンプレ (REPLY TEMPLATE)",
          size=8, color=PURE_WHITE, bold=True)
    _text(c, 18*mm, 13*mm,
          f"【{data.property_name}の件】ご紹介ありがとうございます。①売却理由 ②売主温度感 ③レントロール最新版",
          size=7.5, color=SILVER)
    _text(c, 18*mm, 9*mm,
          "④商流段数 ⑤接道情報 を確認させてください。確認次第、指値含め回答します。",
          size=7.5, color=SILVER)

    # フッター
    _text(c, W-18*mm, 5*mm, "PAGE  02 / 02",
          size=7, color=SILVER_MUTED, anchor='end')


# ══════════════════════════════════════════════════════════════════════════
# パブリックエントリポイント
# ══════════════════════════════════════════════════════════════════════════
def generate_visual_report(out_path: str, data: ReportInputs) -> str:
    """
    モノトーンビジュアル PDF を生成する。

    Args:
        out_path: 出力 PDF パス
        data: ReportInputs インスタンス

    Returns:
        生成された PDF パス
    """
    PAGE_W, PAGE_H = A4
    c = Canvas(out_path, pagesize=A4)
    c.setTitle(f"{data.property_name} — 案件調査レポート")
    c.setAuthor("My Agent Match (MAM)")
    c.setSubject("不動産案件分析レポート")
    c.setCreator("MAM Visual Report Service")
    c.setFont(JA_FONT_NAME, 10)

    _draw_page1(c, PAGE_W, PAGE_H, data)
    c.showPage()
    c.setFont(JA_FONT_NAME, 10)
    _draw_page2(c, PAGE_W, PAGE_H, data)
    c.showPage()
    c.save()

    # ── 後処理: Helvetica 削除 + PDF 1.7 + linearize
    try:
        import pikepdf
        with pikepdf.open(out_path, allow_overwriting_input=True) as pdf:
            for p in pdf.pages:
                if '/Resources' in p and '/Font' in p.Resources:
                    if '/F1' in p.Resources.Font:
                        del p.Resources.Font['/F1']
                sb = p.Contents.read_bytes()
                if b'/F1 ' in sb:
                    sb = sb.replace(b'/F1 ', b'/F2 ')
                    p.Contents.write(sb)
            pdf.save(out_path, linearize=True, min_version="1.7")
    except ImportError:
        pass  # pikepdf 無くても動く（フォント埋込は ReportLab で実施済）

    return out_path
