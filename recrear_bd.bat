@echo off
REM ============================================================
REM  AVACOM - Recrear la base de datos en MySQL (Docker)
REM  Borra las tablas viejas y las crea de nuevo con los tipos
REM  corregidos (fotos/firmas en LONGTEXT). Recarga datos de ejemplo.
REM ============================================================
echo.
echo  Encendiendo MySQL (Docker)...
docker start avacom-mysql

echo.
echo  Conectando a MySQL y recreando las tablas...
set "AVACOM_DB=mysql+pymysql://root:@localhost:3306/avacom_db"

REM Borra el SQLite local si quedo de un intento anterior, para no confundir.
if exist avacom.db del avacom.db

python seed.py

echo.
echo  ============================================================
echo   Si arriba aparecieron los 4 usuarios, la base quedo lista
echo   en MySQL. Ahora puedes arrancar AVACOM con iniciar_avacom.bat
echo  ============================================================
echo.
pause
