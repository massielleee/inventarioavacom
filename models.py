"""AVACOM — Modelos de datos (SQLAlchemy)."""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Text
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime

db = SQLAlchemy()

# Tipo para imágenes y firmas en base64 (data URL).
# En MySQL usa LONGTEXT (hasta 4 GB); en SQLite y otros, Text normal.
# Sin esto, MySQL usa TEXT (máx. 64 KB) y una foto da error 500 al guardarse.
IMG = Text().with_variant(LONGTEXT, "mysql")

# ----------------- USUARIOS Y ROLES -----------------
ROLES = ("ADMIN", "BODEGA", "TECNICO", "CAPACITADOR")

class Usuario(db.Model):
    __tablename__ = "usuario"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="BODEGA")  # ADMIN / BODEGA / TECNICO
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def rol_label(self):
        return {"ADMIN": "Administrador", "BODEGA": "Bodega", "TECNICO": "Técnico",
                "CAPACITADOR": "Capacitador"}.get(self.rol, self.rol)


# ----------------- CATÁLOGOS -----------------
class Categoria(db.Model):
    __tablename__ = "categoria"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    prefijo = db.Column(db.String(6), nullable=False)  # para el SKU, ej. ELEC
    productos = db.relationship("Producto", backref="categoria", lazy=True)


class Marca(db.Model):
    __tablename__ = "marca"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    productos = db.relationship("Producto", backref="marca", lazy=True)


# ----------------- PRODUCTOS -----------------
class Producto(db.Model):
    __tablename__ = "producto"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(30), unique=True, nullable=False)
    codigo_barras = db.Column(db.String(40))  # código escaneado o igual al SKU
    nombre = db.Column(db.String(150), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"))
    marca_id = db.Column(db.Integer, db.ForeignKey("marca.id"))
    precio = db.Column(db.Float, default=0)
    stock = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=5)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def estado(self):
        if self.stock <= 0:
            return "AGOTADO"
        if self.stock <= self.stock_minimo:
            return "BAJO"
        return "ACTIVO"


# ----------------- MOVIMIENTOS DE INVENTARIO -----------------
class Movimiento(db.Model):
    __tablename__ = "movimiento"
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False)  # ENTRADA / SALIDA
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"))
    cantidad = db.Column(db.Integer, nullable=False)
    responsable = db.Column(db.String(150))   # nombre de quien hace el movimiento
    motivo = db.Column(db.String(255))        # para qué lo hizo
    firma = db.Column(IMG)                    # firma dibujada (data URL)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    producto = db.relationship("Producto")
    usuario = db.relationship("Usuario")


# ----------------- DESPACHOS (BODEGA) -----------------
CHECKLIST_ITEMS = [
    "Producto etiquetado con su SKU",
    "Cantidad verificada físicamente",
    "Empaque en buen estado",
    "Datos del destino/cliente confirmados",
    "Documento de salida generado",
]

class Despacho(db.Model):
    __tablename__ = "despacho"
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"))
    cantidad = db.Column(db.Integer, nullable=False)
    destino = db.Column(db.String(150))
    cliente = db.Column(db.String(150))
    motivo = db.Column(db.String(255))
    responsable = db.Column(db.String(150))
    firma = db.Column(IMG)                     # firma al crear el despacho
    firma_checklist = db.Column(IMG)           # firma del checklist al despachar
    remision = db.Column(db.String(20))        # ej. REM-00007
    estado = db.Column(db.String(15), default="PENDIENTE")  # PENDIENTE / DESPACHADO / CANCELADO
    checklist_ok = db.Column(db.Boolean, default=False)
    checklist_json = db.Column(db.Text, default="")  # ítems marcados
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_despacho = db.Column(db.DateTime)
    producto = db.relationship("Producto")
    usuario = db.relationship("Usuario")
    evidencias = db.relationship("EvidenciaDespacho", backref="despacho",
                                 lazy=True, cascade="all, delete-orphan")


class EvidenciaDespacho(db.Model):
    """Foto de evidencia por cada ítem del checklist de despacho."""
    __tablename__ = "evidencia_despacho"
    id = db.Column(db.Integer, primary_key=True)
    despacho_id = db.Column(db.Integer, db.ForeignKey("despacho.id"))
    item_idx = db.Column(db.Integer)      # índice del ítem del checklist
    foto = db.Column(IMG)                 # imagen en data URL
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


# ----------------- GARANTÍAS (TÉCNICO) -----------------
# Checklist que el técnico revisa en la visita técnica
GARANTIA_CHECK = [
    "El equipo enciende correctamente",
    "El equipo apaga correctamente",
    "La pantalla táctil responde",
    "Imagen y sonido funcionan",
    "Conectividad (Wi-Fi / puertos) operativa",
    "Estado físico / carcasa sin daños",
]

class Garantia(db.Model):
    __tablename__ = "garantia"
    id = db.Column(db.Integer, primary_key=True)
    radicado = db.Column(db.String(20), unique=True)  # ej. GAR-00007
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"))
    cliente = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(40))
    descripcion = db.Column(db.Text)                   # por qué / qué le pasó
    # --- contexto del reporte ---
    motivo_dano = db.Column(db.String(255))            # por qué se dañó
    quien_llamo = db.Column(db.String(150))            # quién reportó
    origen_llamada = db.Column(db.String(150))         # de dónde llamó (sede/ciudad)
    tipo_soporte = db.Column(db.String(15), default="PRESENCIAL")  # VIRTUAL / PRESENCIAL
    # --- estado y gestión técnica ---
    estado = db.Column(db.String(20), default="RECIBIDA")  # RECIBIDA / EN_REVISION / SOLUCIONADA / NO_SOLUCIONADA
    requiere_visita = db.Column(db.Boolean, default=False)
    visita_realizada = db.Column(db.Boolean, default=False)
    diagnostico = db.Column(db.Text, default="")       # diagnóstico de la revisión
    solucionado = db.Column(db.Boolean, default=False) # ¿se solucionó?
    motivo_no_solucion = db.Column(db.String(255))     # por qué no se solucionó
    checklist_json = db.Column(db.Text, default="")    # ítems técnicos marcados
    historial = db.Column(db.Text, default="")         # historial de lo que pasó
    firma_tecnico = db.Column(IMG)                     # firma del técnico
    firma_cliente = db.Column(IMG)                     # firma de quien recibe la visita
    remision_tecnica = db.Column(db.String(25))        # ej. REM-TEC-00001
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_visita = db.Column(db.DateTime)              # cuándo se cerró la visita
    producto = db.relationship("Producto")
    tecnico = db.relationship("Usuario")
    evidencias = db.relationship("EvidenciaGarantia", backref="garantia",
                                 lazy=True, cascade="all, delete-orphan")

    @property
    def estado_label(self):
        return {"RECIBIDA": "Recibida", "EN_REVISION": "En revisión",
                "SOLUCIONADA": "Solucionada", "NO_SOLUCIONADA": "No solucionada"}.get(self.estado, self.estado)

    @property
    def soporte_label(self):
        return "Soporte virtual" if self.tipo_soporte == "VIRTUAL" else "Visita presencial"


class EvidenciaGarantia(db.Model):
    """Foto que soporta la visita/gestión técnica."""
    __tablename__ = "evidencia_garantia"
    id = db.Column(db.Integer, primary_key=True)
    garantia_id = db.Column(db.Integer, db.ForeignKey("garantia.id"))
    etiqueta = db.Column(db.String(120))   # qué muestra la foto
    foto = db.Column(IMG)                  # imagen en data URL
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------- CAPACITACIONES (CAPACITADOR) -----------------
import secrets

class Capacitacion(db.Model):
    __tablename__ = "capacitacion"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True)      # ej. CAP-00001
    titulo = db.Column(db.String(180), nullable=False)
    descripcion = db.Column(db.Text)
    capacitador = db.Column(db.String(150))             # nombre de quien capacita
    lugar = db.Column(db.String(180))                   # dónde / enlace de reunión
    modalidad = db.Column(db.String(15), default="PRESENCIAL")  # VIRTUAL / PRESENCIAL
    fecha = db.Column(db.Date)
    hora = db.Column(db.String(10))                     # ej. 14:00
    duracion_est = db.Column(db.String(40))             # duración estimada
    duracion_real = db.Column(db.String(40))            # duración real
    num_esperados = db.Column(db.Integer, default=0)    # asistentes esperados
    token = db.Column(db.String(32), unique=True)       # token del link público de firma
    estado = db.Column(db.String(15), default="ABIERTA")  # ABIERTA / CERRADA
    acta = db.Column(db.String(20))                     # ej. ACTA-00001
    firma_capacitador = db.Column(IMG)
    datos_capacitador = db.Column(db.String(255))       # cargo / documento / contacto
    capacitador_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)
    usuario = db.relationship("Usuario")
    firmas = db.relationship("AsistenteFirma", backref="capacitacion",
                             lazy=True, cascade="all, delete-orphan")
    fotos = db.relationship("FotoCapacitacion", backref="capacitacion",
                            lazy=True, cascade="all, delete-orphan")

    @staticmethod
    def nuevo_token():
        return secrets.token_urlsafe(12)[:16]

    @property
    def modalidad_label(self):
        return "Virtual" if self.modalidad == "VIRTUAL" else "Presencial"

    @property
    def firmados(self):
        return len(self.firmas)


class AsistenteFirma(db.Model):
    """Firma de un asistente recopilada por el link público."""
    __tablename__ = "asistente_firma"
    id = db.Column(db.Integer, primary_key=True)
    capacitacion_id = db.Column(db.Integer, db.ForeignKey("capacitacion.id"))
    nombre = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(40))
    firma = db.Column(IMG)                              # data URL
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class FotoCapacitacion(db.Model):
    """Evidencia fotográfica de que la capacitación se realizó."""
    __tablename__ = "foto_capacitacion"
    id = db.Column(db.Integer, primary_key=True)
    capacitacion_id = db.Column(db.Integer, db.ForeignKey("capacitacion.id"))
    foto = db.Column(IMG)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
