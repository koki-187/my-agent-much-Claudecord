# My Agent Match (MAM)

不動産仲介営業向けのAI案件調査・営業判断支援システムです。

## 目的

売物件情報を受け取った際に、以下を即時判断します。

- 追うべき案件か
- 捨てるべき案件か
- 価格は妥当か
- 指値はいくらが妥当か
- どのリスクを確認すべきか
- どの買主に提案できるか

## セットアップ

```bash
pip install -r requirements.txt
```

## 実行

```bash
python main.py
```

## Webアプリ起動

```bash
streamlit run app/ui/streamlit_app.py
```

または `start.bat` (Windows) を実行

## Streamlit Cloud

https://anken-chosa-kun.streamlit.app

## 出力

`anken_report.md` が生成されます。
