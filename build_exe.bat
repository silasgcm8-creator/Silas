@echo off
chcp 65001 >nul
title SYS CREDIARIO - Gerar executavel
cd /d "%~dp0"

echo ==========================================
echo   SYS CREDIARIO - GERANDO O EXECUTAVEL
echo   Otica Visao
echo ==========================================
echo.

REM ---------------------------------------------------------------
REM Python. O py launcher e mais confiavel que "python" no PATH.
REM ---------------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [ERRO] Python nao encontrado.
    echo.
    echo Instale o Python 3.11 ou superior em:
    echo   https://www.python.org/downloads/windows/
    echo Na primeira tela do instalador marque "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo [1/5] Preparando o ambiente isolado (.venv)...
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar o ambiente .venv
        pause
        exit /b 1
    )
)
set "VPY=.venv\Scripts\python.exe"

echo.
echo [2/5] Instalando as dependencias...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    echo Confira sua conexao com a internet e tente de novo.
    pause
    exit /b 1
)

echo.
echo [3/5] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [4/5] Compilando (pode levar alguns minutos)...
"%VPY%" -m PyInstaller --noconfirm --clean SYS_Crediario.spec
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    echo O detalhe do erro esta acima.
    pause
    exit /b 1
)

if not exist "dist\SYS_Crediario.exe" (
    echo [ERRO] O executavel nao foi encontrado em dist\
    pause
    exit /b 1
)

echo.
echo [5/5] Verificando o executavel gerado...
echo.
REM Roda em area temporaria: nao toca no banco da loja.
REM O cmd nao espera um programa de janela terminar: start /wait resolve.
start /wait "" "dist\SYS_Crediario.exe" --verificar
if errorlevel 1 (
    echo.
    echo [ATENCAO] O executavel foi gerado, mas a verificacao encontrou
    echo problemas. Veja a lista acima antes de usar no balcao.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   PRONTO
echo ==========================================
echo   Programa:  %cd%\dist\SYS_Crediario.exe
echo   Dados:     %USERPROFILE%\SYS_Crediario
echo.
echo   Para criar o icone na Area de Trabalho,
echo   execute agora: criar_atalho.bat
echo.
pause
