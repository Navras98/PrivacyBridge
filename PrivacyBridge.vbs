' PrivacyBridge — launcher Windows silente (nessuna finestra console).
' Doppio click su questo file avvia l'app.  Per associare un'icona
' personalizzata (icon.ico), creare uno shortcut a questo .vbs e nelle
' proprietà dello shortcut impostare "Cambia icona…" -> icon.ico.

Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

dir = fso.GetParentFolderName(WScript.ScriptFullName)
py  = dir & "\venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then
    py = dir & "\venv\Scripts\python.exe"
End If

sh.CurrentDirectory = dir
sh.Run """" & py & """ """ & dir & "\src\avvio.py""", 0, False
