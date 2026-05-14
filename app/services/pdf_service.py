import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)


def _try_reportlab_pdf(report_md: str, output_path: str, property_name: str) -> bool:
    """reportlabでPDFを生成。失敗したらFalseを返す。"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import platform

        # 日本語フォントの登録
        font_registered = False
        if platform.system() == "Windows":
            font_paths = [
                "C:/Windows/Fonts/meiryo.ttc",
                "C:/Windows/Fonts/msgothic.ttc",
                "C:/Windows/Fonts/YuGothM.ttc",
                "C:/Windows/Fonts/YuGothR.ttc",
            ]
        elif platform.system() == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
        else:  # Linux (Streamlit Cloud等)
            font_paths = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

        try:
            for fp in font_paths:
                if os.path.exists(fp):
                    pdfmetrics.registerFont(TTFont("Japanese", fp))
                    font_registered = True
                    break
        except Exception as e:
            logger.warning(f"日本語フォント登録失敗: {e}。Helveticaで代替します。")
            font_registered = False

        jp_font = "Japanese" if font_registered else "Helvetica"

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15*mm, leftMargin=15*mm,
            topMargin=20*mm, bottomMargin=20*mm
        )

        styles = getSampleStyleSheet()
        style_normal = ParagraphStyle("jp_normal", fontName=jp_font, fontSize=9, leading=14)
        style_h1 = ParagraphStyle("jp_h1", fontName=jp_font, fontSize=16, leading=22, spaceAfter=6, textColor=colors.HexColor("#1a1a2e"))
        style_h2 = ParagraphStyle("jp_h2", fontName=jp_font, fontSize=12, leading=18, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor("#16213e"))
        style_bold = ParagraphStyle("jp_bold", fontName=jp_font, fontSize=9, leading=14)

        story = []
        lines = report_md.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 4))
            elif line.startswith("# "):
                story.append(Paragraph(line[2:], style_h1))
                story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e")))
                story.append(Spacer(1, 6))
            elif line.startswith("## "):
                story.append(Paragraph(line[3:], style_h2))
            elif line.startswith("---"):
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
                story.append(Spacer(1, 4))
            elif line.startswith("|"):
                # テーブル行はスキップ（後で処理）
                story.append(Paragraph(line.replace("|", " ").replace("**", ""), style_normal))
            elif line.startswith("- "):
                story.append(Paragraph(f"• {line[2:]}", style_normal))
            elif line.startswith("**") and line.endswith("**"):
                story.append(Paragraph(line.replace("**", ""), style_bold))
            else:
                clean = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
                story.append(Paragraph(clean, style_normal))

        doc.build(story)
        return True
    except ImportError:
        return False
    except Exception as e:
        logger.error("PDF生成エラー: %s", e, exc_info=True)
        return False


def _generate_html_fallback(report_md: str, output_path: str, property_name: str) -> str:
    """HTMLファイルとして出力するフォールバック"""
    html_path = output_path.replace(".pdf", ".html")

    # Markdown→HTML（簡易変換）
    html_lines = []
    for line in report_md.split("\n"):
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("---"):
            html_lines.append("<hr>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.startswith("|"):
            html_lines.append(f"<div class='table-row'>{line}</div>")
        elif line:
            html_lines.append(f"<p>{line}</p>")
        else:
            html_lines.append("<br>")

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>案件調査レポート - {property_name}</title>
<style>
  body {{ font-family: 'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Liberation Sans', sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #1a1a2e; padding-bottom: 8px; }}
  h2 {{ color: #16213e; border-left: 4px solid #4a90e2; padding-left: 12px; margin-top: 24px; }}
  hr {{ border: 0.5px solid #ccc; margin: 16px 0; }}
  li {{ margin: 4px 0; }}
  .table-row {{ font-family: monospace; font-size: 0.9em; }}
  @media print {{ body {{ margin: 20px; }} }}
</style>
</head>
<body>
{''.join(html_lines)}
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return html_path


class PDFService:
    def generate(self, report_md: str, output_path: str = "anken_report.pdf",
                 property_name: str = "案件") -> str:
        success = _try_reportlab_pdf(report_md, output_path, property_name)
        if success:
            return output_path
        else:
            html_path = _generate_html_fallback(report_md, output_path, property_name)
            logger.info("[PDF代替] HTMLファイルとして出力: %s", html_path)
            return html_path
