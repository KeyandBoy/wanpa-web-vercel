@echo off
title WanpaWeb Local Server
cd /d "%~dp0"
set PORT=7732
set PYTHON=python
where python >nul 2>nul || set PYTHON=D:\computerProgram\Anaconda\python.exe
echo Starting local server on port %PORT% ...
start /b "" %PYTHON% local_server.py --port %PORT% >nul 2>&1
powershell -NoProfile -Command "for ($i=0; $i -lt 60; $i++){ try { $r=Invoke-WebRequest -Uri ('http://127.0.0.1:'+$env:PORT+'/api/health') -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
  echo Failed to start server. Please check python and port %PORT%.
  pause
  exit /b 1
)
echo Server ready, opening browser...
start "" http://127.0.0.1:%PORT%/
:loop
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri ('http://127.0.0.1:'+$env:PORT+'/api/health') -UseBasicParsing -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
  timeout /t 5 /nobreak >nul
  goto loop
)
set /a FAILED+=1
if %FAILED% lss 3 (
  timeout /t 3 /nobreak >nul
  goto loop
)
echo Local server exited.
timeout /t 5 /nobreak >nul
exit
