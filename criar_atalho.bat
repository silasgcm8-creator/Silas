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

REM O script PowerShell vai para arquivo temporario: assim caminhos com
REM espaco ou acento nao quebram a linha de comando.
set "PS=%TEMP%\sys_crediario_atalho.ps1"
> "%PS%" echo $alvo = '%ALVO%'
>> "%PS%" echo $pasta = '%cd%\dist'
>> "%PS%" echo $mesa = [Environment]::GetFolderPath('Desktop')
>> "%PS%" echo $shell = New-Object -ComObject WScript.Shell
>> "%PS%" echo $lnk = $shell.CreateShortcut((Join-Path $mesa 'SYS CREDIARIO.lnk'))
>> "%PS%" echo $lnk.TargetPath = $alvo
>> "%PS%" echo $lnk.WorkingDirectory = $pasta
>> "%PS%" echo $lnk.IconLocation = "$alvo,0"
>> "%PS%" echo $lnk.Description = 'SYS CREDIARIO - Otica Visao'
>> "%PS%" echo $lnk.Save()

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%"
set "ERRO=%errorlevel%"
del /q "%PS%" >nul 2>nul

if not "%ERRO%"=="0" (
    echo [ERRO] Nao foi possivel criar o atalho.
    echo Voce pode criar manualmente: clique com o botao direito em
    echo   %ALVO%
    echo e escolha "Enviar para ^> Area de trabalho".
    pause
    exit /b 1
)

echo Atalho "SYS CREDIARIO" criado na Area de Trabalho.
pause
