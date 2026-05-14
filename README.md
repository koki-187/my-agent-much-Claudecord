# 🏢 My Agent Match (MAM)

> **「不動産仲介のプロが、売物件を秒で『追う／捨てる／指値』判断するための AI コパイロット」**

[![tests](https://github.com/koki-187/my-agent-much-Claudecord/actions/workflows/test.yml/badge.svg)](https://github.com/koki-187/my-agent-much-Claudecord/actions/workflows/test.yml)
[![keep-alive](https://github.com/koki-187/my-agent-much-Claudecord/actions/workflows/keep-alive.yml/badge.svg)](https://github.com/koki-187/my-agent-much-Claudecord/actions/workflows/keep-alive.yml)
[![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://my-agent-much.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org)

---

## 🌐 ライブデモ

**▶ https://my-agent-much.streamlit.app**

スマホからもインストール可（PWA 対応）。Safari/Chrome の「ホーム画面に追加」でネイティブアプリと同じ感覚で利用できます。

---

## 💡 何ができる？

物件資料 PDF・メール本文・URL を貼るだけで AI が **30秒で** 以下を弾き出します。

| 機能 | 内容 |
|---|---|
| 🎯 **総合判定** | S/A/B/C/D の 5 段階ランク + 0-100 点総合スコア |
| 💰 **価格妥当性** | 収益還元価格 vs 売出価格 → 「割安/適正/やや高い/高すぎる」判定 |
| 📈 **指値レンジ** | 修繕費・リスク控除を加味した推奨指値（上限/下限） |
| 🏦 **融資シミュ** | DSCR 通常/ストレス、融資可能性 4 段階、想定 LTV |
| 🚪 **出口戦略** | 短期(3年)/中期(5年)/長期(10年) の IRR & 想定売却価格 |
| 🛡️ **リスク検出** | 商流・旧耐震・再建築不可・賃料割高・売主温度感 等 |
| 🔁 **類似過去案件** | エリア×種別×価格×利回り×築年の重み付き類似度 top 3 |
| 🧠 **AI Q&A** | 「この物件、銀行融資通る？」など分析結果ベースで自由質問 |
| 📊 **ビジュアル PDF** | 白・黒・ライトシルバーのモノトーン金融ダッシュボード形式 |

---

## 🚀 主な特長

### 8 物件タイプ対応
一棟マンション / 一棟アパート / 区分マンション / 戸建て / 土地 / 商業 / オフィス / 工場・倉庫

### 18 分析エンジン
PriceEngine / YieldEngine / RiskEngine / ScoringEngine / FinanceEngine / ExitStrategyEngine / RepairCostEngine / RosenkaEngine（路線価DB 209エリア） / AreaTrendEngine（124エリア） / DeveloperLandEngine 他

### マルチプロバイダ LLM
Gemini → OpenAI → Grok → Anthropic Claude の **自動フォールバック**（レート制限耐性）

### モバイル対応 PWA
iOS / Android / Windows / macOS どこからでも「アプリとしてインストール」可能

---

## 📥 セットアップ（ローカル開発）

### 1. リポジトリをクローン

```bash
git clone https://github.com/koki-187/my-agent-much-Claudecord.git
cd my-agent-much-Claudecord
```

### 2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 3. API キーを設定

`.streamlit/secrets.toml` を作成（`.streamlit/secrets.toml.template` を参考に）:

```toml
GEMINI_API_KEY = "AIzaSy..."           # 推奨（無料枠あり）
OPENAI_API_KEY = "sk-proj-..."         # 任意（フォールバック）
ANTHROPIC_API_KEY = "sk-ant-..."       # 任意
APP_PASSWORD = ""                      # 空欄 = 認証スキップ
```

### 4. 起動

```bash
streamlit run app/ui/streamlit_app.py
```

または Windows なら `start.bat` をダブルクリック。

ブラウザで http://localhost:8501 が自動で開きます。

---

## 🧪 テスト実行

```bash
python -m pytest tests/ -v
```

96 件のユニットテスト + 回帰テストが走ります（push 時に GitHub Actions で自動実行）。

---

## 🛠 CLI 利用

```bash
# サンプル物件を分析
python main.py analyze --sample マンション

# 自由テキストから物件抽出
python main.py extract "練馬区 RC造 1995年 1.2億円 表面8.3%"

# 比較レポート
python main.py compare --samples マンション アパート

# バルクスクリーニング
python main.py extract path/to/properties.txt
```

---

## 🏗 アーキテクチャ

```
PropertyData (Pydantic v2)
    └─► DealJudgementService.analyze()
            ├─ 18 Engines (price/yield/risk/...)
            └─► AnalysisResult
                    ├─► ReportGenerator (Markdown 13セクション)
                    └─► VisualReportService (モノトーンPDF 2ページ)
```

詳細は [`CLAUDE.md`](./CLAUDE.md) を参照。

---

## 🌟 UI

- **🏠 ダッシュボード**: 朝開くと S/A/B/C ランク件数・優先案件 top 5・指値検討中を即把握
- **💬 AI チャット入力**: 30 項目入力 → 平均 3 往復のチャットで完成
- **📋 案件分析**: 詳細フォーム → 結果に 🧠 セカンドオピニオン Q&A タブ + 🔁 類似過去案件
- **📦 バルク案件**: 10〜50 物件をテキスト一括貼付で同時判定
- **📊 比較分析**: 保存済み案件を横並びレーダー比較
- **📁 保存済み案件**: 履歴管理・再表示

---

## ⚠️ 免責

本ツールの分析結果は **参考情報** です。投資判断は必ずご自身の責任で行ってください。本サービスは投資助言を行うものではありません。

---

## 📝 ライセンス

Private use only.
