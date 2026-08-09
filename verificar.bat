@echo off
chcp 65001 >nul
title SYS CREDIARIO - Verificar instalacao
cd /d "%~dp0"

REM Confere se tudo que o programa precisa esta funcionando nesta maquina.
REM Roda em area temporaria: os dados da loja nao sao tocados.

if exist "dist\SYS_Crediario.exe" (
    REM O cmd nao espera um programa de janela terminar: start /wait resolve.
start /wait "" "dist\SYS_Crediario.exe" --verificar
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --verificar
) else (
    where py >nul 2>nul && (py -3 main.py --verificar) || (python main.py --verificar)
)

echo.
pause
