
' 案件調査君 サイレントランチャー
' コンソールウィンドウを表示せずにStreamlitを起動し、ブラウザを開きます

Dim shell, fso
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

Dim projectDir
projectDir = "H:\マイドライブ\♦♦♦オリジナル プロダクト♦♦♦\案件調査君\anken-chosa-kun"

Dim streamlit
streamlit = "C:\Users\reale\AppData\Local\Programs\Python\Python313\Scripts\streamlit.exe"

' Streamlit を非表示で起動
Dim cmd
cmd = """" & streamlit & """ run """ & projectDir & "\app\ui\streamlit_app.py"" --server.headless false --browser.gatherUsageStats false"
shell.Run cmd, 0, False

' 3秒待機してからブラウザを開く
WScript.Sleep 3000
shell.Run "http://localhost:8501", 1, False

Set shell = Nothing
Set fso = Nothing
