"""
BuyerMatchingEngine — 用地案件・収益物件とバイヤークライテリアのマッチング

対応バイヤー（2026年版）:
  - GLM（グローバルリンクマネジメント）: マンション用地 / ミニマンション用地
  - フィリックス株式会社: 木造3階アパート用地
  - ケイアイスター不動産: アパート用地（1都13県）
  - GAテクノロジーズ: アパート用地（16号線内側）
  - 株式会社翔栄: 開発用地（都心8区・35〜100坪） / 一棟収益ビル（利回り5%前後）
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BuyerMatchResult:
    """1社分のマッチング結果"""
    buyer_id: str
    buyer_name: str
    buyer_short: str
    dev_type: str

    verdict: str       # "◎ 合致", "○ 条件次第", "△ 要確認", "× 不合致"
    match_score: int   # 0〜100
    summary: str       # 1行コメント

    checks: list[dict]   # [{"item":str, "status":"ok"|"warn"|"ng", "note":str}]
    action: str          # ネクストアクション
    ng_reasons: list[str] = field(default_factory=list)


# ── エリア定義 ────────────────────────────────────────────────────────────────
_TOKYO_23KU = [
    "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
    "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
    "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
    "葛飾区", "江戸川区",
]

_GLM_PREFERRED_WARDS = [
    "渋谷区", "目黒区", "世田谷区", "文京区", "品川区", "新宿区", "中野区", "杉並区",
]

# 16号線（東京環状）内側エリア（主要なもの）
_INSIDE_ROUTE16 = [
    # 東京23区（すべて内側）
    *_TOKYO_23KU,
    # 東京市部（16号線内側）
    "八王子市", "立川市", "武蔵野市", "三鷹市", "府中市", "調布市", "小平市",
    "日野市", "東村山市", "国分寺市", "国立市", "西東京市", "狛江市",
    "東大和市", "清瀬市", "東久留米市", "武蔵村山市", "多摩市", "稲城市",
    "羽村市", "あきる野市", "昭島市", "小金井市", "東大和市",
    # 埼玉（16号線内側）
    "さいたま市", "川口市", "蕨市", "戸田市", "朝霞市", "志木市",
    "和光市", "新座市", "所沢市", "入間市",
    # 神奈川（16号線内側）
    "横浜市", "川崎市", "相模原市",
    # 千葉（16号線内側）
    "千葉市", "市川市", "船橋市", "松戸市", "柏市", "流山市",
    "八千代市", "習志野市", "浦安市",
]

_TERMINAL_AREAS = [
    "新宿区", "渋谷区", "豊島区", "品川区", "港区", "千代田区", "中央区",
    "横浜市", "川崎市", "さいたま市", "千葉市",
]


def _is_tokyo_23ku(address: str) -> bool:
    return any(ku in address for ku in _TOKYO_23KU)


def _is_glm_preferred(address: str) -> bool:
    return any(w in address for w in _GLM_PREFERRED_WARDS)


def _is_inside_route16(address: str) -> bool:
    return any(a in address for a in _INSIDE_ROUTE16)


def _sqm_to_tsubo(sqm: float) -> float:
    return sqm / 3.3058


class BuyerMatchingEngine:
    """
    用地案件をデベロッパーのクライテリアに照合し、
    提案可能バイヤーのリストを返す（土地案件専用）。
    """

    def __init__(self):
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'buyer_criteria.json')
        with open(data_path, encoding='utf-8') as f:
            self._criteria: list[dict] = json.load(f)

    def match(
        self,
        address: str,
        price: int,
        land_area_sqm: Optional[float] = None,
        walk_minutes: Optional[int] = None,
        floor_area_ratio: Optional[float] = None,        # 小数 (2.0 = 200%)
        building_coverage_ratio: Optional[float] = None,
        road_frontage_m: Optional[float] = None,
        road_width_m: Optional[float] = None,
        zoning: Optional[str] = None,
        legal_notes: Optional[str] = None,
        gross_yield: Optional[float] = None,             # 小数 (0.05 = 5%)
        asset_type_str: Optional[str] = None,            # "土地", "一棟マンション" 等
    ) -> list[BuyerMatchResult]:
        """全バイヤーに照合 → スコア降順で返す"""
        results = [
            self._match_one(c, address, price, land_area_sqm, walk_minutes,
                            floor_area_ratio, building_coverage_ratio,
                            road_frontage_m, road_width_m, zoning, legal_notes,
                            gross_yield, asset_type_str)
            for c in self._criteria
        ]
        return sorted(results, key=lambda r: r.match_score, reverse=True)

    # ── 旧 API 互換（ClientData ベース） ──────────────────────────────────────
    def match_clients(self, property_data, clients) -> list[dict]:
        """後方互換ラッパー（旧 ClientData ベース）"""
        from app.models.property import AssetType
        is_land = property_data.asset_type == AssetType.LAND
        is_income = property_data.asset_type in (
            AssetType.APARTMENT_WHOLE, AssetType.APARTMENT_WOOD,
            AssetType.UNIT, AssetType.OFFICE, AssetType.COMMERCIAL,
        )
        if not is_land and not is_income:
            return []
        results = self.match(
            address=property_data.address or "",
            price=property_data.price or 0,
            land_area_sqm=property_data.land_area_sqm,
            floor_area_ratio=property_data.floor_area_ratio,
            building_coverage_ratio=property_data.building_coverage_ratio,
            legal_notes=property_data.legal_notes,
            gross_yield=property_data.gross_yield,
            asset_type_str=property_data.asset_type.value if property_data.asset_type else None,
        )
        return [
            {"client_name": r.buyer_name, "score": r.match_score,
             "reasons": [c["note"] for c in r.checks if c["status"] == "ok"]}
            for r in results if r.match_score >= 40
        ]

    # ── 内部マッチング ─────────────────────────────────────────────────────────
    def _match_one(
        self, c: dict,
        address: str, price: int,
        land_area_sqm, walk_minutes, far, bcr,
        road_frontage_m, road_width_m, zoning, legal_notes,
        gross_yield=None, asset_type_str=None,
    ) -> BuyerMatchResult:

        checks: list[dict] = []
        ng_reasons: list[str] = []
        score = 100

        # 単位変換
        land_tsubo    = _sqm_to_tsubo(land_area_sqm) if land_area_sqm else None
        price_man     = price / 10_000
        ppt_man       = (price_man / land_tsubo) if (land_tsubo and land_tsubo > 0) else None
        far_pct       = (far * 100) if far else None
        bcr_pct       = (bcr * 100) if bcr else None
        yield_pct     = (gross_yield * 100) if gross_yield else None
        buyer_id      = c["buyer_id"]
        ta            = c.get("target_areas", {})
        buyer_asset   = c.get("asset_type", "")

        # ── 0. 物件種別フィルタ ────────────────────────────────────────────────
        # INCOME_BUILDING バイヤーは収益物件のみ、LAND系バイヤーは土地のみ
        if buyer_asset == "INCOME_BUILDING":
            is_income = asset_type_str in (
                "一棟マンション", "一棟アパート", "区分マンション", "オフィス", "商業・店舗"
            )
            if not is_income:
                # 土地案件がインカムバイヤーに来た場合は大幅減点
                if asset_type_str == "土地":
                    score -= 60
                    ng_reasons.append("物件種別不一致（収益物件向けバイヤー）")
        elif buyer_asset in ("LAND", "APARTMENT_WOOD", "MANSION", "MINI_MANSION"):
            # 土地系バイヤーに収益物件が来た場合
            if asset_type_str and asset_type_str not in ("土地",) and buyer_asset == "LAND":
                score -= 60
                ng_reasons.append("物件種別不一致（用地向けバイヤー）")

        # ── 1. エリア ──────────────────────────────────────────────────────────
        if ta.get("tokyo_23ku_only"):
            in_23ku = _is_tokyo_23ku(address)
            status  = "ok" if in_23ku else "ng"
            note    = "東京23区内" if in_23ku else "23区外（GLM買取エリア外）"
            checks.append({"item": "エリア（東京23区）", "status": status, "note": note})
            if not in_23ku:
                score -= 50
                ng_reasons.append("東京23区外")
            elif buyer_id == "GLM_MINI" and _is_glm_preferred(address):
                checks.append({"item": "優先エリア", "status": "ok",
                                "note": "渋谷・目黒・世田谷等の優先8区内"})

        elif ta.get("inside_route16"):
            in_16  = _is_inside_route16(address)
            status = "ok" if in_16 else "ng"
            note   = "16号線内側" if in_16 else "16号線外側（GAテック対象外）"
            checks.append({"item": "エリア（16号線内側）", "status": status, "note": note})
            if not in_16:
                score -= 40
                ng_reasons.append("16号線の外側（GAテックのエリア外）")

        else:
            prefs = ta.get("prefectures", [])
            ok    = any(p in address for p in prefs)
            checks.append({
                "item": "対象エリア",
                "status": "ok" if ok else "ng",
                "note": ta.get("area_note", "") if ok else f"対象外（{ta.get('area_note','')}）",
            })
            if not ok:
                score -= 40
                ng_reasons.append(f"対象エリア外（{ta.get('area_note','')}）")

        # ── 2. 土地面積 ────────────────────────────────────────────────────────
        min_t = c.get("land_area_tsubo_min")
        max_t = c.get("land_area_tsubo_max")
        if min_t or max_t:
            if max_t:
                label = f"土地面積（{min_t or 0}〜{max_t}坪）"
            else:
                label = f"土地面積（≥{min_t}坪）"
            if land_tsubo is None:
                score -= 5
                checks.append({"item": label, "status": "warn", "note": "面積未入力"})
            else:
                ok_min = (min_t is None or land_tsubo >= min_t)
                ok_max = (max_t is None or land_tsubo <= max_t)
                if ok_min and ok_max:
                    checks.append({"item": label, "status": "ok",
                                   "note": f"{land_tsubo:.1f}坪"})
                elif not ok_min:
                    gap = min_t - land_tsubo
                    score -= 25
                    ng_reasons.append(f"土地面積不足（{land_tsubo:.1f}坪 < 最低{min_t}坪）")
                    checks.append({"item": label, "status": "ng",
                                   "note": f"{land_tsubo:.1f}坪（{gap:.0f}坪不足）"})
                else:
                    over = land_tsubo - max_t
                    score -= 20
                    ng_reasons.append(f"土地面積過大（{land_tsubo:.1f}坪 > 上限{max_t}坪）")
                    checks.append({"item": label, "status": "ng",
                                   "note": f"{land_tsubo:.1f}坪（上限{max_t}坪を{over:.0f}坪超過）"})

        # ── 3. 駅徒歩 ──────────────────────────────────────────────────────────
        walk_max      = c.get("walk_minutes_max")
        walk_terminal = c.get("walk_minutes_terminal_max")
        if walk_max:
            if walk_minutes is None:
                score -= 5
                checks.append({"item": f"駅徒歩（≤{walk_max}分）",
                                "status": "warn", "note": "未入力"})
            elif walk_minutes <= walk_max:
                checks.append({"item": f"駅徒歩（≤{walk_max}分）",
                                "status": "ok", "note": f"徒歩{walk_minutes}分"})
            elif walk_terminal and walk_minutes <= walk_terminal:
                score -= 5
                checks.append({"item": f"駅徒歩（≤{walk_max}分）",
                                "status": "warn",
                                "note": f"徒歩{walk_minutes}分（ターミナル駅なら許容）"})
            else:
                penalty = 20 if walk_minutes <= walk_max + 3 else 30
                score -= penalty
                ng_reasons.append(f"駅徒歩超過（{walk_minutes}分 > {walk_max}分）")
                checks.append({"item": f"駅徒歩（≤{walk_max}分）",
                                "status": "ng", "note": f"徒歩{walk_minutes}分"})

        # ── 4. 容積率 ──────────────────────────────────────────────────────────
        far_min = c.get("far_min_pct")
        far_max = c.get("far_max_pct")
        if far_min:
            if far_pct is None:
                score -= 5
                checks.append({"item": f"容積率（≥{far_min}%）",
                                "status": "warn", "note": "未入力"})
            elif far_pct >= far_min:
                if far_max and far_pct > far_max:
                    score -= 10
                    checks.append({"item": f"容積率（{far_min}〜{far_max}%）",
                                   "status": "warn",
                                   "note": f"{far_pct:.0f}%（上限超え、要協議）"})
                else:
                    checks.append({"item": f"容積率（≥{far_min}%）",
                                   "status": "ok", "note": f"{far_pct:.0f}%"})
            else:
                score -= 25
                ng_reasons.append(f"容積率不足（{far_pct:.0f}% < {far_min}%）")
                checks.append({"item": f"容積率（≥{far_min}%）",
                                "status": "ng", "note": f"{far_pct:.0f}%"})

        # ── 5. 建蔽率 ──────────────────────────────────────────────────────────
        bcr_min = c.get("bcr_min_pct")
        if bcr_min:
            if bcr_pct is None:
                checks.append({"item": f"建蔽率（≥{bcr_min}%）",
                                "status": "warn", "note": "未入力"})
            elif bcr_pct >= bcr_min:
                checks.append({"item": f"建蔽率（≥{bcr_min}%）",
                                "status": "ok", "note": f"{bcr_pct:.0f}%"})
            else:
                score -= 10
                checks.append({"item": f"建蔽率（≥{bcr_min}%）",
                                "status": "warn",
                                "note": f"{bcr_pct:.0f}%（{bcr_min}%未満）"})

        # ── 6. 価格 ────────────────────────────────────────────────────────────
        # GAテック：エリア別出口上限
        if buyer_id == "GA_TECH":
            in_23ku    = _is_tokyo_23ku(address)
            in_terminal = any(t in address for t in _TERMINAL_AREAS)
            if in_23ku:
                cap   = c.get("total_price_max_23ku_10000yen", 20000)
                label = f"出口上限（23区：{cap}万円）"
            elif in_terminal:
                cap   = c.get("total_price_max_terminal_10000yen", 18000)
                label = f"出口上限（ターミナル：{cap}万円）"
            else:
                cap   = c.get("total_price_max_other_10000yen", 15000)
                label = f"出口上限（その他：{cap}万円）"

            if price_man <= cap:
                checks.append({"item": label, "status": "ok",
                                "note": f"{price_man:.0f}万円"})
            else:
                score -= 30
                over = price_man - cap
                ng_reasons.append(f"出口価格超過（{price_man:.0f}万円 > 上限{cap}万円）")
                checks.append({"item": label, "status": "ng",
                                "note": f"{price_man:.0f}万円（{over:.0f}万円超過）"})

        # ケイアイスター：総額範囲
        total_min = c.get("total_price_min_10000yen")
        total_max = c.get("total_price_max_10000yen")
        if total_min or total_max:
            if total_max and price_man > total_max:
                score -= 25
                ng_reasons.append(f"総額超過（{price_man:.0f}万円 > {total_max}万円）")
                checks.append({"item": f"総額（〜{total_max}万円）",
                                "status": "ng",
                                "note": f"{price_man:.0f}万円（{price_man - total_max:.0f}万円超）"})
            elif total_min and price_man < total_min:
                score -= 10
                checks.append({"item": f"総額（{total_min}〜{total_max}万円）",
                                "status": "warn",
                                "note": f"{price_man:.0f}万円（下限以下）"})
            else:
                rng = f"{total_min}〜{total_max}万円" if total_min and total_max else f"〜{total_max}万円"
                checks.append({"item": f"総額（{rng}）", "status": "ok",
                                "note": f"{price_man:.0f}万円"})

        # フィリックス：坪単価
        ppt_min = c.get("price_per_tsubo_min_10000yen")
        ppt_max = c.get("price_per_tsubo_max_10000yen")
        if ppt_max:
            if ppt_man is None:
                score -= 5
                checks.append({"item": f"坪単価（{ppt_min}〜{ppt_max}万/坪）",
                                "status": "warn", "note": "面積未入力"})
            elif ppt_man <= ppt_max * 1.1:
                checks.append({"item": f"坪単価（{ppt_min}〜{ppt_max}万/坪）",
                                "status": "ok", "note": f"坪{ppt_man:.0f}万円"})
            else:
                score -= 20
                checks.append({"item": f"坪単価（〜{ppt_max}万/坪）",
                                "status": "warn",
                                "note": f"坪{ppt_man:.0f}万円（都心部は柔軟対応あり）"})

        # ケイアイスター：都心/郊外別坪単価
        urban_max    = c.get("price_per_tsubo_urban_max_10000yen")
        suburban_max = c.get("price_per_tsubo_suburban_max_10000yen")
        if urban_max and ppt_man is not None:
            is_urban = _is_tokyo_23ku(address) or any(
                x in address for x in ["横浜市", "川崎市", "さいたま市", "千葉市"]
            )
            cap   = urban_max if is_urban else suburban_max
            label = "都心" if is_urban else "郊外"
            if ppt_man <= cap:
                checks.append({"item": f"坪単価（{label}≤{cap}万/坪）",
                                "status": "ok", "note": f"坪{ppt_man:.0f}万円"})
            else:
                score -= 20
                checks.append({"item": f"坪単価（{label}≤{cap}万/坪）",
                                "status": "warn",
                                "note": f"坪{ppt_man:.0f}万円（上限超え、要指値）"})

        # ── 6b. 利回りチェック（収益物件バイヤー向け） ────────────────────────
        yield_min = c.get("gross_yield_min_pct")
        yield_max = c.get("gross_yield_max_pct")
        yield_target = c.get("gross_yield_target_pct")
        if yield_min or yield_max or yield_target:
            label_yield = f"表面利回り（{yield_target or yield_min}%前後）"
            if yield_pct is None:
                score -= 10
                checks.append({"item": label_yield, "status": "warn", "note": "利回り未入力"})
            else:
                ok_min = (yield_min is None or yield_pct >= yield_min)
                ok_max = (yield_max is None or yield_pct <= yield_max)
                if ok_min and ok_max:
                    diff = abs(yield_pct - yield_target) if yield_target else 0
                    if diff <= 0.5:
                        checks.append({"item": label_yield, "status": "ok",
                                       "note": f"{yield_pct:.2f}%（ターゲット{yield_target}%に合致）"})
                    else:
                        checks.append({"item": label_yield, "status": "ok",
                                       "note": f"{yield_pct:.2f}%（許容範囲内）"})
                elif not ok_min:
                    short = yield_min - yield_pct
                    score -= 30
                    ng_reasons.append(f"利回り不足（{yield_pct:.2f}% < 最低{yield_min}%）")
                    checks.append({"item": label_yield, "status": "ng",
                                   "note": f"{yield_pct:.2f}%（最低{yield_min}%に{short:.2f}pt不足）"})
                else:
                    # 利回り上限超え（高利回り物件は逆にリスクを示す可能性）
                    checks.append({"item": label_yield, "status": "warn",
                                   "note": f"{yield_pct:.2f}%（上限{yield_max}%超え、高利回り要因を確認）"})
                    score -= 5

        # ── 7. 間口 ────────────────────────────────────────────────────────────
        frontage_min = c.get("road_frontage_min_m")
        if frontage_min:
            if road_frontage_m is None:
                score -= 5
                checks.append({"item": f"間口（≥{frontage_min}m）",
                                "status": "warn", "note": "未入力"})
            elif road_frontage_m >= frontage_min:
                checks.append({"item": f"間口（≥{frontage_min}m）",
                                "status": "ok", "note": f"間口{road_frontage_m}m"})
            else:
                score -= 20
                ng_reasons.append(f"間口不足（{road_frontage_m}m < {frontage_min}m）")
                checks.append({"item": f"間口（≥{frontage_min}m）",
                                "status": "ng",
                                "note": f"{road_frontage_m}m（{frontage_min}m未満）"})

        # ── 8. NG条件 ──────────────────────────────────────────────────────────
        ng_list = c.get("ng_conditions", [])
        legal = legal_notes or ""
        for ng in ng_list:
            hit = (
                ("擁壁2m超え"     in ng and "擁壁" in legal) or
                ("但し書き個人所有" in ng and "但し書き" in legal) or
                ("殺人・宗教"     in ng and ("殺人" in legal or "宗教" in legal)) or
                ("低容積率"        in ng and far_pct is not None and far_pct < 150)
            )
            if hit:
                score -= 40
                ng_reasons.append(f"NG条件: {ng}")
                checks.append({"item": f"NG: {ng}", "status": "ng", "note": "検討不可"})

        # ── 9. 想定戸数（GLM） ─────────────────────────────────────────────────
        units_min = c.get("units_min")
        if units_min and land_tsubo and far_pct:
            floor_sqm   = land_tsubo * 3.3058 * (far_pct / 100) * 0.95
            est_units   = int(floor_sqm * 0.70 / 25.0)  # ワンルーム平均25㎡
            if est_units >= units_min:
                checks.append({"item": f"想定戸数（≥{units_min}戸）",
                                "status": "ok", "note": f"推定{est_units}戸"})
            else:
                score -= 20
                checks.append({"item": f"想定戸数（≥{units_min}戸）",
                                "status": "warn",
                                "note": f"推定{est_units}戸（{units_min}戸に届かない可能性）"})

        # ── 判定 ───────────────────────────────────────────────────────────────
        score     = max(0, min(100, score))
        hard_ng   = len(ng_reasons) > 0

        if score >= 75 and not hard_ng:
            verdict = "◎ 合致"
        elif score >= 50 and len(ng_reasons) <= 1:
            verdict = "○ 条件次第"
        elif score >= 30:
            verdict = "△ 要確認"
        else:
            verdict = "× 不合致"

        summary = self._summary(c, verdict, ng_reasons, ppt_man, land_tsubo)
        action  = self._action(c, verdict, ng_reasons, price_man, ppt_man, land_tsubo, address)

        return BuyerMatchResult(
            buyer_id    = buyer_id,
            buyer_name  = c["buyer_name"],
            buyer_short = c["buyer_short"],
            dev_type    = c["dev_type"],
            verdict     = verdict,
            match_score = score,
            summary     = summary,
            checks      = checks,
            action      = action,
            ng_reasons  = ng_reasons,
        )

    # ── テキスト生成 ───────────────────────────────────────────────────────────
    def _summary(self, c, verdict, ng_reasons, ppt, land_tsubo) -> str:
        name = c["buyer_short"]
        if verdict == "◎ 合致":
            return f"{name}のクライテリアに合致。即打診可能。"
        elif verdict == "○ 条件次第":
            issue = ng_reasons[0] if ng_reasons else "一部条件の詰め"
            return f"{name}に打診可能。「{issue}」の確認・解消が先決。"
        elif verdict == "△ 要確認":
            issue = ng_reasons[0] if ng_reasons else "追加情報収集"
            return f"{name}への提案は「{issue}」次第。情報確認が必要。"
        else:
            issue = ng_reasons[0] if ng_reasons else "クライテリアとの乖離"
            return f"{name}は「{issue}」により現状不合致。"

    def _action(self, c, verdict, ng_reasons, price_man, ppt, land_tsubo, address) -> str:
        name     = c["buyer_short"]
        buyer_id = c["buyer_id"]
        land_str = f"土地{land_tsubo:.0f}坪" if land_tsubo else "土地面積確認要"
        price_str = f"総額{price_man:.0f}万円"

        if verdict in ("◎ 合致", "○ 条件次第"):
            if buyer_id in ("GLM_MANSION", "GLM_MINI"):
                return (f"GLM担当者へ非公式ヒアリング："
                        f"「{address}の{land_str}・容積率条件で検討できますか？」と打診")
            elif buyer_id == "FELIX":
                tstr = f"坪{ppt:.0f}万円" if ppt else "坪単価確認要"
                return (f"フィリックス担当に物件概要を送付（{tstr}・{land_str}）。"
                        f"ZEH仕様アパートとして利回り試算を依頼")
            elif buyer_id == "KAISTAR":
                return (f"ケイアイスター担当に物件概要をメール送付。"
                        f"{price_str}・{land_str}で検討依頼。駅徒歩・容積率を明記")
            elif buyer_id == "GA_TECH":
                return (f"GAテック担当に物件情報を送付。"
                        f"16号線内側・{price_str}の出口価格帯に合う案件として打診")
            elif buyer_id == "SHOEI_LAND":
                return (f"翔栄担当者に物件概要を送付。"
                        f"{address}の{land_str}・{price_str}で開発用地として検討を依頼。"
                        f"容積率・用途地域を明記すること")
            elif buyer_id == "SHOEI_INCOME":
                return (f"翔栄担当者に物件概要を送付。"
                        f"{address}・{price_str}の一棟収益ビルとして提案。"
                        f"利回り・現況賃料・稼働率を必ず添付")
        elif verdict == "△ 要確認":
            if ng_reasons:
                return f"「{ng_reasons[0]}」を先に確認・解消。解消できれば{name}に打診可能"
            return f"{name}への打診前に駅徒歩・間口・容積率等の追加情報を収集"
        return f"{name}への提案は現状困難。他バイヤーへの提案を優先"
