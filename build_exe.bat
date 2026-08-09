@echo off
chcp 65001 >nul
title SYS CREDIARIO - Gerar executavel
cd /d "%~dp0"

echo ==========================================
echo   SYS CREDIARIO - GERANDO O EXECUTAVEL
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Instale o Python 3.11 ou superior marcando "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    pause
    exit /b 1
)

echo.
echo [2/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist SYS_Crediario.spec del /q SYS_Crediario.spec

echo.
echo [3/4] Compilando com PyInstaller...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --noconsole ^
    --name "SYS_Crediario" ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "sqlalchemy.dialects.sqlite" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.protocols.websockets.auto" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --collect-submodules "app" ^
    main.py
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    pause
    exit /b 1
)

echo.
echo [4/4] Concluido!
echo O programa esta em:  %cd%\dist\SYS_Crediario.exe
echo Os dados ficam em:   %USERPROFILE%\SYS_Crediario\data
echo.
pause
