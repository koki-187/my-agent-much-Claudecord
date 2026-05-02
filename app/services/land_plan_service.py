from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


ARCHITECT_SYSTEM_PROMPT = """あなたは東京で30年のキャリアを持つ一級建築士です。
都市計画法・建築基準法に精通し、高層マンション・商業施設・ホテル・工場の設計経験が豊富です。

与えられた用地情報（容積率・建蔽率・道路幅員・用途地域・面積）を元に、
以下の観点から建築計画の実現可能性と注意点を分析してください：

1. **建築可能規模と構造提案**
   - 最大延床面積と想定階数（各プランタイプ別）
   - 推奨構造（RC/S/木造/混構造）とその理由
   - 間取りプランの基本構成

2. **法規制・制限のチェック**
   - 道路幅員による容積率緩和・制限（前面道路×法定乗数）
   - 日影規制・斜線制限の影響
   - 防火地域・準防火地域の制限
   - セットバック必要性（4m未満道路）

3. **建築コスト感**
   - 構造・規模別のおおよそのコスト感
   - 地盤・解体・杭工事リスク

4. **実現可能性評価**
   - 各プランタイプ（1K投資/ファミリー/商業/オフィス/ホテル/工場）について○△×で評価
   - 最も実現性が高いプランとその根拠

回答は実際の設計経験に基づいた具体的な数値・根拠を含めて、200字程度で各項目を答えてください。"""


LAND_ACQUISITIONER_SYSTEM_PROMPT = """あなたは大手デベロッパーで15年間用地仕入れを担当してきたプロフェッショナルです。
年間50件以上の用地査定経験を持ち、「この土地でいくら出せるか」の即断即決が得意です。

与えられた用地情報と各プランのシミュレーション結果を元に、
以下の観点から土地仕入れの実務的判断を行ってください：

1. **土地価格の妥当性評価**
   - 各プランで逆算したデベ最大買値と売出価格の比較
   - 「追う/条件次第/捨てる」の明確な判断と根拠
   - 指値の具体的な根拠と切り口

2. **仕入れリスクの整理**
   - 最大のリスクは何か（価格・法規・市場・競合）
   - リスクヘッジの方法

3. **バイヤーマッチングの実務判断**
   - このプランならどのデベに持ち込むか（具体的な会社名イメージ）
   - 提案する際の「売り文句」

4. **タイムライン評価**
   - 仕入れから竣工・引き渡しまでの概算スケジュール
   - 市場タイミングリスク

実務担当者として「現場感覚」を大切にした、歯切れのよい判断を200字程度で各項目に答えてください。"""


ECONOMIST_SYSTEM_PROMPT = """あなたは不動産・建設業界専門の経済アナリストです。
マクロ経済から不動産市場の需給動向、金利影響、エリア別の相場分析まで精通しています。

与えられた用地情報と各プランのシミュレーション結果を元に、
以下の観点から経済分析を行ってください：

1. **市場需給分析**
   - このエリア・プランタイプの需給バランス
   - 競合物件との差別化ポイント
   - 需要吸収期間の見通し

2. **収益性・IRR分析**
   - 投資利回りとキャップレートの水準評価
   - 金利上昇シナリオでの影響試算（+0.5%, +1.0%）
   - 最適プランのNOI・FCFシミュレーション概算

3. **周辺相場との乖離分析**
   - 一種単価・二種単価の相場水準との比較
   - 過去3年のエリア価格トレンドとの整合性

4. **経済環境リスク**
   - マクロリスク（金利・景気・人口動態）の影響
   - このプランへの具体的な影響度

データと数字を使った定量的な分析を200字程度で各項目に答えてください。"""


SALES_SYSTEM_PROMPT = """あなたは大手デベロッパーのマンション・商業施設の販売企画担当です。
エンドユーザーへの販売から法人テナント誘致まで、幅広い販売戦略の立案経験があります。

与えられた用地情報と各プランのシミュレーション結果を元に、
以下の観点から販売戦略を提案してください：

1. **ターゲットユーザー分析**
   - 最適プランのターゲット層（属性・ニーズ）
   - このエリアでの購買動機とライフスタイル

2. **価格設定戦略**
   - 適正分譲価格・賃料の設定根拠
   - 周辺競合との差別化のポイント
   - 値引きリスクの評価

3. **販売スピード・吸収力**
   - 売れ行き見通し（即完/6ヶ月/1年以内/長期）
   - 在庫リスクの大小

4. **最終推奨プランと理由**
   - 「このプランにすべき」という販売担当としての結論
   - バイヤー企業・投資家へのピッチポイント

購入者・テナントの目線に立ったリアルな販売感覚で200字程度で各項目に答えてください。"""


OVERALL_RECOMMENDATION_SYSTEM_PROMPT = """あなたは不動産プロ向け総合アドバイザーです。
一級建築士・用地仕入れ担当・経済アナリスト・販売担当の4名の専門家分析を統合し、
以下の形式で最終推奨レポートを出力してください：

## 🏆 最終推奨プラン
[最もお勧めのプランを1つ明示]

## 📋 推奨理由（3点）
1. [理由1]
2. [理由2]
3. [理由3]

## ⚠️ 主要リスク
[最大の懸念点を2点]

## 💼 推奨バイヤー（優先順）
1. [バイヤータイプ] — [この価格なら動く可能性高]
2. [バイヤータイプ] — [指値交渉で検討可能]
3. [バイヤータイプ] — [長期的に検討価値あり]

## 💰 適正価格の目線
- 現在売値: X万円
- 推奨指値価格: X万円（現値から△X%）
- 最低ライン: X万円

## ✅ 今すぐやるべきアクション（3ステップ）
1. [ステップ1]
2. [ステップ2]
3. [ステップ3]"""


class LandPlanAnalysisService:
    def __init__(self):
        from app.services.llm_service import _get_client
        self.client = _get_client()
        self.available = self.client is not None

    def analyze_all_experts(
        self,
        land_info: str,
        scenarios_summary: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """
        4名の専門家全員の分析を並列実行して返す。
        返値: {
            "architect": str,
            "land_acquisitioner": str,
            "economist": str,
            "sales": str,
            "overall_recommendation": str,
        }
        """
        user_content = f"【用地情報】\n{land_info}\n\n【各プランシミュレーション】\n{scenarios_summary}"

        experts = {
            "architect": ARCHITECT_SYSTEM_PROMPT,
            "land_acquisitioner": LAND_ACQUISITIONER_SYSTEM_PROMPT,
            "economist": ECONOMIST_SYSTEM_PROMPT,
            "sales": SALES_SYSTEM_PROMPT,
        }

        results: dict[str, str] = {}
        total = len(experts)
        done_count = [0]

        import threading
        lock = threading.Lock()

        def _run(key: str, system_prompt: str) -> tuple[str, str]:
            result = self._run_expert(system_prompt, user_content)
            return key, result

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(_run, key, prompt): key
                for key, prompt in experts.items()
            }
            for future in as_completed(futures):
                key, result = future.result()
                with lock:
                    results[key] = result
                    done_count[0] += 1
                    if progress_callback:
                        try:
                            progress_callback(done_count[0] - 1, total)
                        except Exception:
                            pass

        overall = self.generate_overall_recommendation(
            land_info=land_info,
            scenarios_summary=scenarios_summary,
            expert_analyses=results,
        )
        results["overall_recommendation"] = overall
        return results

    def generate_overall_recommendation(
        self,
        land_info: str,
        scenarios_summary: str,
        expert_analyses: dict,
    ) -> str:
        """
        4名の専門家分析を統合した最終推奨を生成。
        モデル: claude-sonnet-4-6, max_tokens: 3000
        """
        if not self.available:
            return ""

        expert_text = (
            f"【一級建築士の分析】\n{expert_analyses.get('architect', '')}\n\n"
            f"【用地仕入れ担当の分析】\n{expert_analyses.get('land_acquisitioner', '')}\n\n"
            f"【経済アナリストの分析】\n{expert_analyses.get('economist', '')}\n\n"
            f"【販売担当の分析】\n{expert_analyses.get('sales', '')}"
        )
        user_content = (
            f"【用地情報】\n{land_info}\n\n"
            f"【各プランシミュレーション】\n{scenarios_summary}\n\n"
            f"{expert_text}"
        )

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                system=OVERALL_RECOMMENDATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"[LandPlan総合推奨エラー] {e}")
            return ""

    def _run_expert(self, system_prompt: str, user_content: str) -> str:
        """単一専門家の分析を実行"""
        if not self.available:
            return ""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            return response.content[0].text
        except Exception as e:
            print(f"[LandPlan専門家分析エラー] {e}")
            return ""

    @staticmethod
    def build_land_info_text(
        address: str,
        price: int,
        land_area_sqm: float,
        far: float,
        bcr: float,
        road_width_m: Optional[float],
        zoning: Optional[str],
        walk_minutes: Optional[int],
    ) -> str:
        """用地情報テキストを生成"""
        lines = [
            f"所在地: {address}",
            f"売出価格: {price // 10000:,}万円（{price:,}円）",
            f"土地面積: {land_area_sqm:.1f}㎡（{land_area_sqm / 3.30579:.1f}坪）",
            f"容積率: {far:.0f}%",
            f"建蔽率: {bcr:.0f}%",
        ]
        if road_width_m is not None:
            lines.append(f"前面道路幅員: {road_width_m:.1f}m")
        if zoning:
            lines.append(f"用途地域: {zoning}")
        if walk_minutes is not None:
            lines.append(f"最寄駅徒歩: {walk_minutes}分")
        return "\n".join(lines)

    @staticmethod
    def build_scenarios_summary_text(scenarios: list) -> str:
        """プランシナリオのサマリーテキストを生成（各PlanScenarioのテキスト化）"""
        if not scenarios:
            return "シミュレーション結果なし"

        lines = []
        for i, scenario in enumerate(scenarios, start=1):
            # PlanScenario オブジェクトまたは dict の両方に対応
            if isinstance(scenario, dict):
                name = scenario.get("plan_name") or f"プラン{i}"
                feasible = scenario.get("is_feasible", True)
                total_floor = scenario.get("estimated_floor_area_sqm")
                gross_yield = scenario.get("gross_yield_pct")
                noi = scenario.get("noi_annual")
                max_land_price = scenario.get("max_land_price")
                total_rev = scenario.get("total_revenue")
                price_eval = scenario.get("land_price_evaluation", "")
                rec = scenario.get("recommendation", "")
                score = scenario.get("score", 0)
            else:
                name = getattr(scenario, "plan_name", f"プラン{i}")
                feasible = getattr(scenario, "is_feasible", True)
                total_floor = getattr(scenario, "estimated_floor_area_sqm", None)
                gross_yield = getattr(scenario, "gross_yield_pct", None)
                noi = getattr(scenario, "noi_annual", None)
                max_land_price = getattr(scenario, "max_land_price", None)
                total_rev = getattr(scenario, "total_revenue", None)
                price_eval = getattr(scenario, "land_price_evaluation", "")
                rec = getattr(scenario, "recommendation", "")
                score = getattr(scenario, "score", 0)

            feas_mark = "○実現可能" if feasible else "×実現困難"
            parts = [f"■ {name}（{feas_mark}・スコア{score}点・{rec}）"]
            if total_floor is not None:
                parts.append(f"  延床面積: {total_floor:.0f}㎡")
            if total_rev is not None:
                parts.append(f"  想定売上/評価額: {total_rev // 10000:,}万円")
            if max_land_price is not None:
                parts.append(f"  デベ最大買値: {max_land_price // 10000:,}万円（価格評価: {price_eval}）")
            if gross_yield is not None:
                parts.append(f"  利回り: {gross_yield:.1f}%")
            if noi is not None:
                parts.append(f"  NOI（年間）: {noi // 10000:,}万円")
            lines.append("\n".join(parts))

        return "\n\n".join(lines)
