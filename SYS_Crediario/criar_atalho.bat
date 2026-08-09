@echo off
chcp 65001 >nul
title SYS CREDIARIO - Criar atalho na Area de Trabalho
cd /d "%~dp0"

set "ALVO=%cd%\dist\SYS_Crediario.exe"
if not exist "%ALVO%" (
    echo [AVISO] O executavel ainda nao existe.
    echo Rode primeiro o arquivo build_exe.bat.
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\SYS CREDIARIO.lnk');" ^
  "$s.TargetPath='%ALVO%';" ^
  "$s.WorkingDirectory='%cd%\dist';" ^
  "$s.IconLocation='%ALVO%,0';" ^
  "$s.Description='SYS CREDIARIO - controle de crediario';" ^
  "$s.Save()"

echo Atalho "SYS CREDIARIO" criado na Area de Trabalho.
pause
