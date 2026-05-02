@echo off
chcp 65001 > nul
title My Agent Much (MAM)

echo.
echo  ╔══════════════════════════════════╗
echo  ║     My Agent Much (MAM) 起動中...  ║
echo  ╚══════════════════════════════════╝
echo.

cd /d "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\My Agent Much\my-agent-much"

:: Streamlit 起動（ブラウザ自動オープン）
start "" "C:\Users\reale\AppData\Local\Programs\Python\Python313\Scripts\streamlit.exe" run app/ui/streamlit_app.py --server.headless false --browser.gatherUsageStats false

:: 少し待ってからブラウザを開く
timeout /t 3 /nobreak > nul
start http://localhost:8501

echo  起動完了！ブラウザが開かない場合は http://localhost:8501 を開いてください。
echo  このウィンドウを閉じるとアプリが停止します。
echo.
pause
