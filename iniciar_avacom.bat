@echo off
REM ====================================================
REM   AVACOM - Arranque automatico con MySQL (Docker)
REM   Doble clic en este archivo para iniciar el sistema
REM ====================================================
title AVACOM - Servidor

echo.
echo   ====================================
echo      INICIANDO AVACOM
echo   ====================================
echo.

REM 1) Asegurar que el contenedor MySQL de Docker este encendido
echo   [1/3] Encendiendo la base de datos MySQL en Docker...
docker start avacom-mysql >nul 2>&1

REM 2) Darle unos segundos a MySQL para que este listo
echo   [2/3] Esperando a que MySQL este listo...
timeout /t 6 /nobreak >nul

REM 3) Conectar AVACOM a ese MySQL (sintaxis de CMD, no PowerShell)
set AVACOM_DB=mysql+pymysql://root:@localhost:3306/avacom_db

echo   [3/3] Iniciando el servidor AVACOM...
echo.
echo   Cuando veas "Running on http://127.0.0.1:8080"
echo   abre tu navegador en:  http://localhost:8080
echo.
echo   Usuarios:
echo      Admin        admin@avacom.co / admin123
echo      Bodega       bodega@avacom.co / bodega123
echo      Tecnico      tecnico@avacom.co / tecnico123
echo      Capacitador  capacitador@avacom.co / capacita123
echo.
echo   Para DETENER el sistema: cierra esta ventana o pulsa Ctrl+C
echo   ====================================
echo.

REM Arrancar el servidor (este .bat debe estar en la carpeta avacom_app)
python app.py

pause
