# My Agent Much (MAM) — Claude Code ガイド

このファイルはClaude Codeが自動で読み込む。新規セッションでも即座に作業を開始できるよう設計されている。

---

## プロジェクト概要

**My Agent Much (MAM)** — 不動産仲介営業向けAI案件調査・営業判断支援システム

- 売物件情報を受け取った際に「追うべきか・捨てるべきか・指値はいくらか」を即時判断
- Python 3.13 / Streamlit / Google Gemini API（またはAnthropic Claude API）
- マルチOS対応 Web UI（Windows・macOS・Linux・iOS Safari）

---

## 重要パス・リポジトリ

| 項目 | 値 |
|---|---|
| ローカルパス | `H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Much\my-agent-much` |
| GitHub | `https://github.com/koki-187/my-agent-much-Claudecord` (branch: master) |
| Streamlit Cloud | `https://my-agent-much.streamlit.app` |
| Google Drive | `https://drive.google.com/drive/folders/1ic5VLpsVJIdA3jk6_MaRPIisK5O7GAZo` |
| Python実行環境 | `C:\Users\reale\AppData\Local\Programs\Python\Python313\python.exe` |
| Streamlit実行環境 | `C:\Users\reale\AppData\Local\Programs\Python\Python313\Scripts\streamlit.exe` |

---

## アプリ起動方法

```bash
# ローカル起動（開発用）
cd "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Much\my-agent-much"
streamlit run app/ui/streamlit_app.py

# サイレント起動（ブラウザ自動オープン）
wscript start_silent.vbs

# または専用バッチ
start.bat

# リモートアクセス対応起動（LAN・スマホから）
streamlit run app/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

アプリURL: `http://localhost:8501`

---

## API設定

### ローカル環境
`.streamlit/secrets.toml`（.gitignore対象）に記載：
```toml
GEMINI_API_KEY = "AIzaSy..."   # Google Gemini（メイン）
ANTHROPIC_API_KEY = ""         # Claude（フォールバック）
APP_PASSWORD = ""              # 空欄=認証スキップ
```

テンプレート: `.streamlit/secrets.toml.template`

### Streamlit Cloud
`share.streamlit.io` のApp Settings → Secrets に同じ内容を設定済み。

---

## ディレクトリ構造

```
my-agent-much/
├── app/
│   ├── engines/           # 分析エンジン群（18本）
│   │   ├── price_engine.py         # 収益還元価格・価格妥当性
│   │   ├── yield_engine.py         # 利回り計算
│   │   ├── risk_engine.py          # リスク検出（商流/資料/修繕/法的）
│   │   ├── scoring_engine.py       # 総合スコア算出（0-100点）
│   │   ├── offer_engine.py         # 指値レンジ算出
│   │   ├── development_engine.py   # 開発ポテンシャル評価
│   │   ├── asset_type_engine.py    # 8種別対応（一棟/アパート/区分/戸建て/土地/商業/オフィス/工場）
│   │   ├── rosenka_engine.py       # 路線価DB（全国209エリア）
│   │   ├── finance_engine.py       # 融資シミュレーション（DSCR/ストレス金利）
│   │   ├── exit_strategy_engine.py # 出口戦略3シナリオ（3/5/10年・IRR）
│   │   ├── repair_cost_engine.py   # 修繕費積算（2024年建築費高騰対応）
│   │   ├── area_trend_engine.py    # エリアトレンドDB（全国124エリア）
│   │   ├── next_action_engine.py   # 次の一手レコメンド
│   │   ├── buyer_matching_engine.py # 買主マッチング
│   │   ├── developer_land_engine.py # デベ用地逆算価格
│   │   ├── bulk_extractor.py        # バルク一括スクリーニング
│   │   └── land_plan_engine.py      # 土地プラン試算
│   ├── models/            # データモデル（Pydantic v2）
│   │   ├── property.py    # PropertyData / AssetType（8種別Enum）
│   │   ├── client.py      # ClientData
│   │   ├── analysis_result.py
│   │   └── land_plan.py
│   ├── services/          # サービス層
│   │   ├── deal_judgement_service.py  # 全エンジン統合・メインオーケストレーター
│   │   ├── llm_service.py             # Gemini/Claude API連携・テキスト抽出
│   │   ├── report_generator.py        # 13セクションMarkdownレポート生成
│   │   ├── storage_service.py         # JSON/CSV履歴保存・重複検知
│   │   ├── comparison_service.py      # 複数案件比較
│   │   ├── pdf_service.py             # PDF生成（reportlab）
│   │   ├── hearing_generator.py       # ヒアリング項目生成
│   │   └── land_plan_service.py
│   ├── ui/
│   │   └── streamlit_app.py  # メインUI（4ページ: 案件分析/バルク/比較/履歴）
│   ├── prompts/           # LLMプロンプト
│   │   ├── analysis_prompt.md
│   │   ├── hearing_prompt.md
│   │   └── report_prompt.md
│   ├── data/              # CSVデータベース
│   │   ├── rent_market.csv          # 賃料相場DB
│   │   ├── area_market.csv          # エリア市場DB
│   │   ├── area_trends.csv          # エリアトレンドDB
│   │   ├── buyer_criteria.json      # 買主条件DB
│   │   ├── dev_land_market.csv      # 開発用地市場DB
│   │   ├── rosenka.csv              # 路線価DB
│   │   ├── clients.csv              # 顧客DBサンプル
│   │   ├── sample_deals.json        # サンプル物件データ
│   │   └── land_plan_benchmarks.json
│   ├── static/
│   │   └── mam_logo/      # MAMロゴ（21サイズ: 16x16〜1024x1024 PNG）
│   └── utils/
│       └── logger.py      # RotatingFileHandler（logs/mam.log）
├── tests/                 # pytest（42テスト）
│   ├── test_price_engine.py    (8テスト)
│   ├── test_risk_engine.py     (8テスト)
│   ├── test_scoring_engine.py  (10テスト)
│   └── test_new_engines.py     (16テスト)
├── main.py                # CLI（analyze/batch/compare/list/extract）
├── requirements.txt       # 依存パッケージ
├── start.bat              # Windows起動バッチ
├── start_silent.vbs       # サイレント起動（コンソール非表示）
├── create_shortcut.vbs    # デスクトップショートカット作成
├── .streamlit/
│   ├── config.toml
│   ├── secrets.toml       # ★gitignore（API keyはここに）
│   └── secrets.toml.template
└── CLAUDE.md              # このファイル
```

---

## コアアーキテクチャ

### 分析フロー
```
PropertyData (Pydantic)
    └─► DealJudgementService.analyze()
            ├─ PriceEngine        → 価格妥当性・収益還元価格
            ├─ YieldEngine        → 実質利回り計算
            ├─ RiskEngine         → リスク検出（商流/資料/修繕/法的）
            ├─ DevelopmentEngine  → 容積率・建替ポテンシャル
            ├─ ScoringEngine      → 6軸スコア → 総合スコア(0-100)
            ├─ OfferEngine        → 指値レンジ（基準価格×係数）
            ├─ RosenkaEngine      → 路線価マッチング（209エリア）
            ├─ FinanceEngine      → 融資シミュレーション
            ├─ ExitStrategyEngine → 出口戦略3シナリオ
            ├─ RepairCostEngine   → 修繕費積算
            ├─ AreaTrendEngine    → エリアトレンド取得
            ├─ NextActionEngine   → 次の一手レコメンド
            ├─ DeveloperLandEngine→ デベ用地逆算価格
            └─ BuyerMatchingEngine→ 買主マッチング
                    ↓
            AnalysisResult
                    ↓
            ReportGenerator → Markdownレポート（13セクション）
```

### ランク基準
| ランク | スコア | 判断 |
|---|---|---|
| S | 85+ | 即対応・重点案件 |
| A | 70〜84 | 条件次第で積極検討 |
| B | 55〜69 | 指値前提で検討 |
| C | 40〜54 | 基本様子見・追加確認後判断 |
| D | 0〜39 | 原則追わない |

### UIページ構成（streamlit_app.py）
1. **📋 案件分析** — 物件入力フォーム → AI分析 → KPI/スコア/レポート表示
2. **📦 バルク案件** — テキスト一括貼り付け → 複数物件同時スクリーニング
3. **📊 比較分析** — 保存済み案件を横並び比較
4. **📁 保存済み案件** — 履歴管理・再表示

### LLMサービス（llm_service.py）
- **プロバイダー優先順位**: Gemini → OpenAI → Grok（xAI） → Anthropic Claude（自動フォールバック）
- **フォールバック条件**: HTTP 429（レート制限）またはプロバイダエラー時に次プロバイダへ自動切替
- **モデルマッピング（OpenAI）**: haiku/sonnet → gpt-4o-mini、opus → gpt-4o
- **モデルマッピング（Grok）**: haiku → grok-3-mini-fast、sonnet → grok-3-mini、opus → grok-3
- Streamlit Cloud: `st.secrets` から自動読み込み（GEMINI/OPENAI/GROK/ANTHROPIC _API_KEY）
- ローカル: `.streamlit/secrets.toml` または `MAM.env` ファイル
- 機能: テキスト抽出（物件情報テキスト→PropertyDataJSON）、AIアドバイス生成
- **注意**: Grokは console.x.ai でのクレジット購入が必要（未購入時は 403 エラーでスキップ）

---

## 開発コマンド

```bash
# テスト実行
cd "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Much\my-agent-much"
python -m pytest tests/ -v

# CLI分析（サンプル）
python main.py analyze --sample マンション

# テキストからAI抽出
python main.py extract "練馬区 RC造 1995年 120000万円 表面8.3%"

# 比較レポート
python main.py compare --samples マンション アパート

# インストール
pip install -r requirements.txt
```

---

## ブランドガイドライン（UI）

- **アプリ名**: My Agent Much（略称: MAM）
- **ロゴ**: `app/static/mam_logo/mam_Xxtw_Xpx.png`（UIにbase64埋め込み）
- **カラーパレット**:
  - Primary Blue: `#2563EB` / Light: `#60A5FA`
  - Dark BG: `#0A1628` → `#1A2A50`（サイドバーグラデーション）
  - Text Dark: `#0F172A`
  - Amber Accent: `#F59E0B` / `#FBBF24`
  - Success Green: `#10B981`
  - BG: `#F0F4F8`
- **フォント**: Noto Sans JP / Hiragino Sans / Yu Gothic UI / Meiryo
- **CSS**: `app/ui/streamlit_app.py` 内インラインCSS（〜300行）
  - iOS対応: font-size 16px最低保証、タッチターゲット44px
  - レスポンシブ: 1024px / 768px / 480px ブレークポイント
  - 印刷対応: `@media print`
  - 数値等幅: `font-variant-numeric: tabular-nums`

---

## Streamlit Cloud 設定

- URL: `https://my-agent-much.streamlit.app`
- 接続すべきリポジトリ: `koki-187/my-agent-much-Claudecord`（masterブランチ）
- Main file: `app/ui/streamlit_app.py`
- Secrets（share.streamlit.io → App Settings → Secrets）:
  ```toml
  GEMINI_API_KEY = "AIzaSy..."   # ★ secrets.toml と同じキーを設定（ここには書かない）
  APP_PASSWORD = ""
  ```

---

## Windows 起動スクリプト（C:\Users\reale\）

| ファイル | 用途 |
|---|---|
| `mam_start.vbs` | ダブルクリックで起動（コンソール非表示）|
| `mam_start.bat` | バッチ起動（パス: `My Agent Much\my-agent-much`）|

デスクトップショートカット再作成:
```
wscript "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Much\my-agent-much\create_shortcut.vbs"
```

---

## 未完了タスク（2026-05-11時点）

### 任意対応
1. **Grokクレジット購入**: console.x.ai でクレジット購入後、Grokフォールバックが機能するようになる

### 完了済み
- ✅ 外側フォルダリネーム: `案件調査君` → `My Agent Much`
- ✅ 全スクリプトのパス更新（start.bat / start_silent.vbs / create_shortcut.vbs）
- ✅ Windows起動スクリプト: `mam_start.vbs` / `mam_start.bat` 作成（C:\Users\reale\）
- ✅ CLAUDE.md の全パス参照を新パスに更新
- ✅ ルクレ三田・グランデュオ祖師谷II の個別システム分析（case_studies/ 参照）
- ✅ 3物件ギャップ分析レポート完成（case_studies/gap_analysis_report.md）
- ✅ マルチプロバイダLLMフォールバック実装（Gemini→OpenAI→Grok→Anthropic）
- ✅ 賃料相場DB大幅拡充（33行→165行、一都3県＋大阪・京都・神戸・名古屋・福岡ほか）
- ✅ 賃料リスク判定ロジック全面強化（築年補正係数・賃貸可能面積対応・割安判定追加）
- ✅ Streamlit Cloud Secrets 更新（GEMINI新キー＋OPENAI_API_KEY追加）
- ✅ Streamlit Cloud リポジトリ確認（my-agent-much-claudecord・master・正常接続済み）

---

## 注意事項

- `.streamlit/secrets.toml` は `.gitignore` 対象。GitにはAPIキーを絶対にコミットしない
- `app/data/history/` は個人情報含む可能性があり `.gitignore` 対象
- `Pillow` は requirements.txt に含まれているが、Streamlit自体も依存しているため通常自動インストール済み
- ロゴ読み込み失敗時はフォールバックとして 🤖 絵文字を表示
- `MAM.env` ファイルはローカル開発時のみ使用（パス: プロジェクトルート直上）
