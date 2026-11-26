# AVACOM — Sistema de gestión (SENA ADSO)

Sistema web para la gestión de inventario, despachos, garantías y capacitaciones
de **AVACOM** (ecosistemas educativos: tableros inteligentes, tablets, mesas interactivas).

Construido en **Python (Flask) + MySQL**. Diseño rojo/blanco, 4 roles.

---

## Usuarios de prueba

| Rol         | Correo                   | Contraseña   | Puede ver                                  |
|-------------|--------------------------|--------------|--------------------------------------------|
| Admin       | admin@avacom.co          | admin123     | Todo el sistema + Usuarios + Capacitaciones |
| Bodega      | bodega@avacom.co         | bodega123    | Productos, Movimientos, Despachos           |
| Técnico     | tecnico@avacom.co        | tecnico123   | Productos, Garantías                        |
| Capacitador | capacitador@avacom.co    | capacita123  | Capacitaciones                              |

---

## Cómo ejecutarlo en tu PC (Windows)

### 1. Abre una terminal DENTRO de la carpeta del proyecto
Descomprime el ZIP. Entra a la carpeta `avacom_app`. En la barra de direcciones
del explorador de archivos escribe `cmd` y presiona Enter: se abre una terminal
ya ubicada en esa carpeta.

### 2. Instala las dependencias (una sola vez)
En esa terminal:

    pip install -r requirements.txt

### 3. Base de datos MySQL con Docker (la que usamos)

**La forma más fácil: doble clic en `iniciar_avacom.bat`.**
Ese archivo enciende el MySQL de Docker, conecta el sistema y arranca el
servidor automáticamente. Si lo usas, sáltate el resto de esta sección.

**Si prefieres hacerlo a mano**, levanta el MySQL en Docker (una sola vez):

    docker run --name avacom-mysql -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=avacom_db -p 3306:3306 -d mysql:8.0

Si el contenedor ya existe y solo está apagado:

    docker start avacom-mysql

Luego conecta el sistema. **OJO con la terminal:**

- En **PowerShell** (la de Windows moderna):

       $env:AVACOM_DB = "mysql+pymysql://root:@localhost:3306/avacom_db"

- En **CMD** (la terminal negra clásica):

       set AVACOM_DB=mysql+pymysql://root:@localhost:3306/avacom_db

> Importante: en PowerShell `set` NO funciona para esto; hay que usar `$env:`.
> Si la variable no queda bien, el sistema usa un archivo SQLite local
> (`avacom.db`) en vez de MySQL. Verifícala con:
>
>     python -c "import os; print(os.environ.get('AVACOM_DB'))"
>
> Debe imprimir la dirección de MySQL, no `None`.

Crea las tablas y los datos de ejemplo:

    python seed.py

### 4. Arranca el servidor

    python app.py

Abre el navegador en **http://localhost:8080** e inicia sesión con un usuario
de la tabla de arriba.

### Ver las tablas en MySQL Workbench (para la sustentación)
Crea una conexión nueva: Hostname `127.0.0.1`, Port `3306`, Username `root`,
Password vacío. Entra y expande `avacom_db` -> `Tables`.

---

## Qué hace cada módulo

- **Productos**: catálogo con SKU único automático por categoría (AVC-TABL-00001),
  código de barras imprimible. Se pueden crear categorías nuevas al vuelo.
- **Movimientos** (Bodega): entradas/salidas de stock, con responsable y firma.
- **Despachos** (Bodega): checklist con foto de evidencia obligatoria por ítem,
  firma, y **remisión PDF** automática al despachar.
- **Garantías** (Técnico): checklist de revisión, diagnóstico, historial, fotos,
  doble firma (técnico + cliente) y **remisión técnica PDF** al cerrar la visita.
- **Capacitaciones** (Capacitador): agenda, **link público + QR** de firma de
  asistencia, evidencias, firma del capacitador y **acta de asistencia PDF** con
  todos los firmantes. Pestañas Pendientes/Realizadas y archivo histórico.
- **Usuarios** (Admin): gestión de usuarios y roles, con re-autenticación por
  seguridad al entrar.

---

## Notas técnicas

- La **remisión y el acta** se "descargan en PDF" usando la impresión del
  navegador (Ctrl+P → Guardar como PDF).
- El **link de firma de asistencia** se genera listo para compartir; el envío
  masivo real por correo/WhatsApp se haría con un servicio de correo en
  producción (no incluido en esta versión local).
- `qrcode` genera el código QR; va incluido en `requirements.txt`.

Stack: Flask, Flask-SQLAlchemy, Werkzeug (hash de contraseñas), PyMySQL, qrcode.
