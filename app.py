"""AVACOM — Sistema de gestión de inventario. App principal (Flask)."""
import os, json
from functools import wraps
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort)
from models import (db, Usuario, Categoria, Marca, Producto, Movimiento,
                    Despacho, Garantia, CHECKLIST_ITEMS, EvidenciaDespacho,
                    GARANTIA_CHECK, EvidenciaGarantia,
                    Capacitacion, AsistenteFirma, FotoCapacitacion)
from servicios import (generar_sku, generar_radicado, registrar_movimiento,
                       codigo_barras_svg, generar_remision, generar_remision_tecnica,
                       generar_codigo_capacitacion, generar_acta)
from datetime import date
from flask import Response

app = Flask(__name__)
app.config["SECRET_KEY"] = "avacom-sena-2026-massielle"
# Permitir subir fotos de evidencia (data URL) sin error 413 "Payload Too Large".
# Las fotos se comprimen en el navegador, pero subimos el límite por seguridad.
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024        # 25 MB por petición
try:
    # Werkzeug >= 3.1 limita el tamaño de los campos de formulario por separado.
    app.config["MAX_FORM_MEMORY_SIZE"] = 25 * 1024 * 1024
    app.config["MAX_FORM_PARTS"] = 2000
except Exception:
    pass

# --- Base de datos: MySQL si hay variable, si no SQLite (para demo sin instalar nada) ---
# En local se usa AVACOM_DB. En la nube (Railway) la variable puede llamarse
# MYSQL_URL o DATABASE_URL, así que las aceptamos todas.
DB_URL = (os.environ.get("AVACOM_DB")
          or os.environ.get("MYSQL_URL")
          or os.environ.get("DATABASE_URL"))
if DB_URL:
    # Railway suele entregar la URL como "mysql://..."; SQLAlchemy necesita el
    # driver PyMySQL, así que normalizamos el prefijo.
    if DB_URL.startswith("mysql://"):
        DB_URL = DB_URL.replace("mysql://", "mysql+pymysql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(os.path.dirname(__file__), "avacom.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Reconectar si la conexión a MySQL se cae (común en la nube)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True, "pool_recycle": 280}
db.init_app(app)


def inicializar_datos():
    """Crea las tablas y carga los datos de ejemplo SOLO si la base está vacía.
    Se ejecuta al arrancar en la nube, para no tener que correr seed.py a mano.
    No borra nada: si ya hay usuarios, no hace nada."""
    with app.app_context():
        db.create_all()
        if Usuario.query.first() is not None:
            return  # ya inicializada, no tocar
        # usuarios por rol
        admin = Usuario(nombre="Massielle Julio", correo="admin@avacom.co", rol="ADMIN"); admin.set_password("admin123")
        bod = Usuario(nombre="Carlos Bodega", correo="bodega@avacom.co", rol="BODEGA"); bod.set_password("bodega123")
        tec = Usuario(nombre="Laura Técnica", correo="tecnico@avacom.co", rol="TECNICO"); tec.set_password("tecnico123")
        cap = Usuario(nombre="Andrés Capacitador", correo="capacitador@avacom.co", rol="CAPACITADOR"); cap.set_password("capacita123")
        db.session.add_all([admin, bod, tec, cap]); db.session.commit()
        # categorías educativas
        cats = {}
        for nom, pref in [("Tableros inteligentes", "TABL"), ("Tablets educativas", "TBLT"),
                          ("Mesas interactivas", "MESA"), ("Accesorios", "ACCE")]:
            c = Categoria(nombre=nom, prefijo=pref); db.session.add(c); cats[nom] = c
        marca = Marca(nombre="AVACOM"); db.session.add(marca); db.session.commit()
        data = [
            ("Tablero inteligente 75\" 4K táctil", "Tableros inteligentes", 7800000, 12, 4),
            ("Tablero inteligente 86\" 4K táctil", "Tableros inteligentes", 9500000, 5, 3),
            ("Tablet educativa 10\" infantil", "Tablets educativas", 850000, 60, 15),
            ("Tablet educativa 8\" preescolar", "Tablets educativas", 620000, 8, 10),
            ("Mesa interactiva infantil 43\"", "Mesas interactivas", 5400000, 6, 3),
            ("Lápiz óptico para tablero", "Accesorios", 120000, 40, 12),
            ("Soporte con ruedas para tablero", "Accesorios", 980000, 3, 5),
        ]
        prods = []
        for nombre, cat, precio, stock, smin in data:
            c = cats[cat]
            p = Producto(sku=generar_sku(c), nombre=nombre, categoria_id=c.id,
                         marca_id=marca.id, precio=precio, stock=stock, stock_minimo=smin)
            db.session.add(p); db.session.commit(); prods.append(p)
        g = Garantia(radicado=generar_radicado(), producto_id=prods[0].id,
                     cliente="Colegio San José", telefono="3101234567",
                     descripcion="El tablero no registra el táctil en el borde derecho.",
                     motivo_dano="Golpe durante instalación",
                     quien_llamo="Coord. Diana Páez", origen_llamada="Sede Norte - Bogotá",
                     tipo_soporte="PRESENCIAL", estado="EN_REVISION", requiere_visita=True,
                     tecnico_id=tec.id)
        db.session.add(g); db.session.commit()
        print("Base de datos inicializada con datos de ejemplo.")


# ----------------- CONTROL DE ACCESO -----------------
def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        if "uid" not in session:
            return redirect(url_for("login"))
        return fn(*a, **k)
    return wrapper

def rol_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            if "uid" not in session:
                return redirect(url_for("login"))
            if session.get("rol") not in roles:
                flash("No tienes permiso para acceder a esa sección.", "error")
                return redirect(url_for("dashboard"))
            return fn(*a, **k)
        return wrapper
    return deco

@app.context_processor
def inject_user():
    u = Usuario.query.get(session["uid"]) if "uid" in session else None
    return dict(current_user=u)


# ----------------- AUTENTICACIÓN -----------------
@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("dashboard") if "uid" in session else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        pwd = request.form.get("password", "")
        u = Usuario.query.filter_by(correo=correo).first()
        if u and u.activo and u.check_password(pwd):
            session["uid"] = u.id
            session["rol"] = u.rol
            session["nombre"] = u.nombre
            return redirect(url_for("dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------- DASHBOARD -----------------
@app.route("/dashboard")
@login_required
def dashboard():
    rol = session.get("rol")
    hoy = datetime.utcnow().date()
    stats = {
        "productos": Producto.query.count(),
        "stock_total": db.session.query(db.func.coalesce(db.func.sum(Producto.stock), 0)).scalar(),
        "bajo_stock": sum(1 for p in Producto.query.all() if p.estado in ("BAJO", "AGOTADO")),
        "movimientos_hoy": Movimiento.query.filter(db.func.date(Movimiento.fecha) == hoy).count(),
        "despachos_pendientes": Despacho.query.filter_by(estado="PENDIENTE").count(),
        "garantias_abiertas": Garantia.query.filter(Garantia.estado.in_(["RECIBIDA", "EN_REVISION"])).count(),
    }
    ultimos = Producto.query.order_by(Producto.id.desc()).limit(6).all()
    meses_es = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
    hoy_txt = f"{hoy.day} de {meses_es[hoy.month-1]} de {hoy.year}"
    barras = [
        {"lbl": "Productos",  "val": stats["productos"],          "color": "#D7263D"},
        {"lbl": "Stock",      "val": stats["stock_total"],        "color": "#1E9E62"},
        {"lbl": "Bajo stock", "val": stats["bajo_stock"],         "color": "#C8820E"},
        {"lbl": "Movim. hoy", "val": stats["movimientos_hoy"],    "color": "#2A6DD0"},
        {"lbl": "Despachos",  "val": stats["despachos_pendientes"],"color": "#8E44AD"},
        {"lbl": "Garantías",  "val": stats["garantias_abiertas"], "color": "#7A1420"},
    ]
    return render_template("dashboard.html", stats=stats, ultimos=ultimos, rol=rol,
                           hoy_txt=hoy_txt, barras=barras)


# ----------------- PRODUCTOS -----------------
@app.route("/productos")
@login_required
def productos():
    q = request.args.get("q", "").strip()
    query = Producto.query
    if q:
        query = query.filter(db.or_(Producto.nombre.ilike(f"%{q}%"), Producto.sku.ilike(f"%{q}%")))
    items = query.order_by(Producto.id.desc()).all()
    return render_template("productos.html", items=items, q=q)

@app.route("/productos/nuevo", methods=["GET", "POST"])
@rol_required("ADMIN")
def producto_nuevo():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    if request.method == "POST":
        # permitir crear categoría al vuelo sin un módulo de catálogos aparte
        if request.form.get("categoria") == "__nueva__":
            nueva = request.form.get("nueva_categoria", "").strip()
            pref = request.form.get("nuevo_prefijo", "").strip().upper()[:6]
            if nueva and pref:
                cat = Categoria(nombre=nueva, prefijo=pref)
                db.session.add(cat)
                db.session.commit()
            else:
                flash("Para una categoría nueva indica nombre y prefijo.", "error")
                return redirect(url_for("producto_nuevo"))
        else:
            cat = Categoria.query.get(int(request.form["categoria"]))
        sku = generar_sku(cat)
        # marca AVACOM por defecto (interna)
        marca = Marca.query.first()
        p = Producto(
            sku=sku,
            codigo_barras=(request.form.get("codigo_barras") or "").strip() or sku,
            nombre=request.form["nombre"].strip(),
            categoria_id=cat.id,
            marca_id=marca.id if marca else None,
            precio=float(request.form.get("precio") or 0),
            stock=int(request.form.get("stock") or 0),
            stock_minimo=int(request.form.get("stock_minimo") or 5),
        )
        db.session.add(p)
        db.session.commit()
        flash(f"Producto registrado con SKU {p.sku}.", "ok")
        return redirect(url_for("producto_detalle", pid=p.id))
    return render_template("producto_form.html", cats=cats)

@app.route("/productos/<int:pid>")
@login_required
def producto_detalle(pid):
    p = Producto.query.get_or_404(pid)
    return render_template("producto_detalle.html", p=p)

@app.route("/barcode/<path:code>.svg")
@login_required
def barcode_svg(code):
    return Response(codigo_barras_svg(code), mimetype="image/svg+xml")


# ----------------- MOVIMIENTOS -----------------
@app.route("/movimientos", methods=["GET", "POST"])
@rol_required("ADMIN", "BODEGA")
def movimientos():
    if request.method == "POST":
        p = Producto.query.get(int(request.form["producto"]))
        firma = request.form.get("firma", "")
        if not request.form.get("responsable", "").strip():
            flash("Debes indicar el nombre del responsable.", "error")
            return redirect(url_for("movimientos"))
        if not firma or len(firma) < 100:
            flash("La firma es obligatoria para registrar el movimiento.", "error")
            return redirect(url_for("movimientos"))
        ok, msg = registrar_movimiento(
            p, request.form["tipo"], request.form["cantidad"], session["uid"],
            responsable=request.form.get("responsable", "").strip(),
            motivo=request.form.get("motivo", "").strip(),
            firma=firma)
        flash(msg, "ok" if ok else "error")
        return redirect(url_for("movimientos"))
    items = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(30).all()
    productos = Producto.query.order_by(Producto.nombre).all()
    return render_template("movimientos.html", items=items, productos=productos)

@app.route("/movimientos/<int:mid>")
@rol_required("ADMIN", "BODEGA")
def movimiento_detalle(mid):
    m = Movimiento.query.get_or_404(mid)
    return render_template("movimiento_detalle.html", m=m)


# ----------------- DESPACHOS (BODEGA) -----------------
@app.route("/despachos")
@rol_required("ADMIN", "BODEGA")
def despachos():
    items = Despacho.query.order_by(Despacho.id.desc()).all()
    return render_template("despachos.html", items=items)

@app.route("/despachos/nuevo", methods=["GET", "POST"])
@rol_required("ADMIN", "BODEGA")
def despacho_nuevo():
    if request.method == "POST":
        firma = request.form.get("firma", "")
        if not request.form.get("responsable", "").strip():
            flash("Debes indicar el responsable del despacho.", "error")
            return redirect(url_for("despacho_nuevo"))
        if not firma or len(firma) < 100:
            flash("La firma es obligatoria para crear el despacho.", "error")
            return redirect(url_for("despacho_nuevo"))
        d = Despacho(
            producto_id=int(request.form["producto"]),
            cantidad=int(request.form["cantidad"]),
            destino=request.form["destino"].strip(),
            cliente=request.form.get("cliente", "").strip(),
            motivo=request.form.get("motivo", "").strip(),
            responsable=request.form.get("responsable", "").strip(),
            firma=firma,
            usuario_id=session["uid"],
        )
        db.session.add(d)
        db.session.commit()
        flash("Despacho creado. Completa el checklist con evidencias para poder despacharlo.", "ok")
        return redirect(url_for("despacho_detalle", did=d.id))
    productos = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).all()
    return render_template("despacho_form.html", productos=productos)

@app.route("/despachos/<int:did>", methods=["GET", "POST"])
@rol_required("ADMIN", "BODEGA")
def despacho_detalle(did):
    d = Despacho.query.get_or_404(did)
    if request.method == "POST":
        accion = request.form.get("accion")
        if accion == "subir_evidencia":
            idx = int(request.form["item_idx"])
            foto = request.form.get("foto", "")
            if foto:
                ev = EvidenciaDespacho.query.filter_by(despacho_id=d.id, item_idx=idx).first()
                if ev:
                    ev.foto = foto
                else:
                    db.session.add(EvidenciaDespacho(despacho_id=d.id, item_idx=idx, foto=foto))
                # marcar ítem como hecho
                marcados = set(json.loads(d.checklist_json) if d.checklist_json else [])
                marcados.add(CHECKLIST_ITEMS[idx])
                d.checklist_json = json.dumps(list(marcados))
                # checklist ok si todas las fotos están
                n_fotos = EvidenciaDespacho.query.filter_by(despacho_id=d.id).count()
                d.checklist_ok = (n_fotos >= len(CHECKLIST_ITEMS))
                db.session.commit()
                flash("Evidencia registrada.", "ok")
        elif accion == "firmar_checklist":
            firma = request.form.get("firma_checklist", "")
            if firma and len(firma) > 100:
                d.firma_checklist = firma
                db.session.commit()
                flash("Checklist firmado.", "ok")
            else:
                flash("La firma del checklist es obligatoria.", "error")
        elif accion == "despachar":
            n_fotos = EvidenciaDespacho.query.filter_by(despacho_id=d.id).count()
            if n_fotos < len(CHECKLIST_ITEMS):
                flash("Faltan fotos de evidencia en el checklist.", "error")
            elif not d.firma_checklist:
                flash("Debes firmar el checklist antes de despachar.", "error")
            elif d.cantidad > d.producto.stock:
                flash("Stock insuficiente para despachar.", "error")
            else:
                ok, msg = registrar_movimiento(
                    d.producto, "SALIDA", d.cantidad, session["uid"],
                    responsable=d.responsable, motivo="Despacho " + (d.destino or ""),
                    firma=d.firma_checklist)
                if ok:
                    d.estado = "DESPACHADO"
                    d.fecha_despacho = datetime.utcnow()
                    d.remision = generar_remision()
                    db.session.commit()
                    flash(f"¡Producto despachado! Remisión {d.remision} generada.", "ok")
                    return redirect(url_for("remision", did=d.id))
                else:
                    flash(msg, "error")
        return redirect(url_for("despacho_detalle", did=d.id))
    marcados = json.loads(d.checklist_json) if d.checklist_json else []
    evidencias = {e.item_idx: e.foto for e in d.evidencias}
    return render_template("despacho_detalle.html", d=d, checklist_items=CHECKLIST_ITEMS,
                           marcados=marcados, evidencias=evidencias)

@app.route("/despachos/<int:did>/remision")
@rol_required("ADMIN", "BODEGA")
def remision(did):
    d = Despacho.query.get_or_404(did)
    if d.estado != "DESPACHADO":
        flash("La remisión se genera cuando el despacho está completado.", "error")
        return redirect(url_for("despacho_detalle", did=d.id))
    return render_template("remision.html", d=d, checklist_items=CHECKLIST_ITEMS)


# ----------------- GARANTÍAS (TÉCNICO) -----------------
@app.route("/garantias")
@rol_required("ADMIN", "TECNICO")
def garantias():
    items = Garantia.query.order_by(Garantia.id.desc()).all()
    return render_template("garantias.html", items=items)

# ==================== BORRADO (solo ADMIN) ====================
# Para dejar el sistema limpio antes de una prueba o demo.
# Las evidencias/firmas/fotos se borran solas por el cascade de los modelos.

@app.route("/garantias/<int:gid>/eliminar", methods=["POST"])
@rol_required("ADMIN")
def garantia_eliminar(gid):
    g = Garantia.query.get_or_404(gid)
    db.session.delete(g)
    db.session.commit()
    flash("Garantía eliminada.", "ok")
    return redirect(url_for("garantias"))

@app.route("/despachos/<int:did>/eliminar", methods=["POST"])
@rol_required("ADMIN")
def despacho_eliminar(did):
    d = Despacho.query.get_or_404(did)
    db.session.delete(d)
    db.session.commit()
    flash("Despacho eliminado.", "ok")
    return redirect(url_for("despachos"))

@app.route("/capacitaciones/<int:cid>/eliminar", methods=["POST"])
@rol_required("ADMIN")
def capacitacion_eliminar(cid):
    c = Capacitacion.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash("Capacitación eliminada.", "ok")
    return redirect(url_for("capacitaciones"))

@app.route("/productos/<int:pid>/eliminar", methods=["POST"])
@rol_required("ADMIN")
def producto_eliminar(pid):
    p = Producto.query.get_or_404(pid)
    # Los productos no tienen cascade, así que limpiamos sus movimientos primero.
    Movimiento.query.filter_by(producto_id=p.id).delete()
    db.session.delete(p)
    db.session.commit()
    flash("Producto eliminado.", "ok")
    return redirect(url_for("productos"))

@app.route("/admin/limpiar", methods=["POST"])
@rol_required("ADMIN")
def admin_limpiar():
    """Deja el sistema limpio para una prueba: borra garantías, despachos,
    capacitaciones y movimientos. Los productos y usuarios se conservan."""
    Garantia.query.delete()
    Despacho.query.delete()
    for c in Capacitacion.query.all():
        db.session.delete(c)   # uno por uno para que el cascade borre firmas/fotos
    Movimiento.query.delete()
    db.session.commit()
    flash("Sistema limpio: se eliminaron garantías, despachos, capacitaciones y movimientos.", "ok")
    return redirect(url_for("dashboard"))

@app.route("/garantias/nueva", methods=["GET", "POST"])
@rol_required("ADMIN", "TECNICO")
def garantia_nueva():
    if request.method == "POST":
        g = Garantia(
            radicado=generar_radicado(),
            producto_id=int(request.form["producto"]),
            cliente=request.form["cliente"].strip(),
            telefono=request.form.get("telefono", "").strip(),
            descripcion=request.form.get("descripcion", "").strip(),
            motivo_dano=request.form.get("motivo_dano", "").strip(),
            quien_llamo=request.form.get("quien_llamo", "").strip(),
            origen_llamada=request.form.get("origen_llamada", "").strip(),
            tipo_soporte=request.form.get("tipo_soporte", "PRESENCIAL"),
            requiere_visita=(request.form.get("tipo_soporte") == "PRESENCIAL"),
            tecnico_id=session["uid"],
        )
        db.session.add(g)
        db.session.commit()
        flash(f"Garantía registrada con radicado {g.radicado}.", "ok")
        return redirect(url_for("garantia_detalle", gid=g.id))
    productos = Producto.query.order_by(Producto.nombre).all()
    return render_template("garantia_form.html", productos=productos)

@app.route("/garantias/<int:gid>", methods=["GET", "POST"])
@rol_required("ADMIN", "TECNICO")
def garantia_detalle(gid):
    g = Garantia.query.get_or_404(gid)
    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "marcar_check":
            # guardar un ítem del checklist al instante: estado "ok" o "falla"
            item = request.form.get("item", "")
            valor = request.form.get("valor", "")   # ok | falla | (vacío = quitar)
            estados = json.loads(g.checklist_json) if g.checklist_json else {}
            if not isinstance(estados, dict):       # compatibilidad con formato viejo (lista)
                estados = {x: "ok" for x in estados}
            if item in GARANTIA_CHECK:
                if valor in ("ok", "falla"):
                    estados[item] = valor
                else:
                    estados.pop(item, None)
            g.checklist_json = json.dumps(estados)
            if g.estado == "RECIBIDA":
                g.estado = "EN_REVISION"
            db.session.commit()
            # respuesta ligera para el fetch (sin recargar la página)
            return jsonify(ok=True, item=item, valor=estados.get(item, ""))

        elif accion == "guardar_gestion":
            # diagnóstico + historial + por qué/para qué/por quién
            g.diagnostico = request.form.get("diagnostico", "").strip()
            g.historial = request.form.get("historial", "").strip()
            g.motivo_dano = request.form.get("motivo_dano", g.motivo_dano or "").strip()
            g.quien_llamo = request.form.get("quien_llamo", g.quien_llamo or "").strip()
            g.origen_llamada = request.form.get("origen_llamada", g.origen_llamada or "").strip()
            if g.estado == "RECIBIDA":
                g.estado = "EN_REVISION"
            db.session.commit()
            flash("Gestión técnica guardada.", "ok")

        elif accion == "subir_evidencia":
            foto = request.form.get("foto", "")
            etiqueta = request.form.get("etiqueta", "Evidencia").strip()
            if foto:
                db.session.add(EvidenciaGarantia(
                    garantia_id=g.id, etiqueta=etiqueta, foto=foto))
                db.session.commit()
                flash("Evidencia agregada.", "ok")

        elif accion == "borrar_evidencia":
            ev = EvidenciaGarantia.query.get(int(request.form["ev_id"]))
            if ev and ev.garantia_id == g.id:
                db.session.delete(ev)
                db.session.commit()
                flash("Evidencia eliminada.", "ok")

        elif accion == "firmar_tecnico":
            firma = request.form.get("firma_tecnico", "")
            if firma and len(firma) > 100:
                g.firma_tecnico = firma
                db.session.commit()
                flash("Firma del técnico guardada.", "ok")
            else:
                flash("La firma del técnico es obligatoria.", "error")

        elif accion == "firmar_cliente":
            firma = request.form.get("firma_cliente", "")
            if firma and len(firma) > 100:
                g.firma_cliente = firma
                db.session.commit()
                flash("Firma del cliente guardada.", "ok")
            else:
                flash("La firma del cliente es obligatoria.", "error")

        elif accion == "cerrar_visita":
            # emitir la remisión técnica cuando la visita se completa
            resuelto = request.form.get("solucionado") == "si"
            faltan = []
            if not g.firma_tecnico:
                faltan.append("firma del técnico")
            if not g.firma_cliente:
                faltan.append("firma del cliente")
            if EvidenciaGarantia.query.filter_by(garantia_id=g.id).count() == 0:
                faltan.append("al menos una foto de evidencia")
            if not g.diagnostico:
                faltan.append("diagnóstico")
            if faltan:
                flash("Para cerrar la visita falta: " + ", ".join(faltan) + ".", "error")
            else:
                g.solucionado = resuelto
                g.motivo_no_solucion = ("" if resuelto
                                        else request.form.get("motivo_no_solucion", "").strip())
                g.estado = "SOLUCIONADA" if resuelto else "NO_SOLUCIONADA"
                g.visita_realizada = True
                g.fecha_visita = datetime.utcnow()
                g.remision_tecnica = generar_remision_tecnica()
                db.session.commit()
                flash(f"Visita cerrada. Remisión {g.remision_tecnica} generada.", "ok")
                return redirect(url_for("remision_garantia", gid=g.id))

        return redirect(url_for("garantia_detalle", gid=g.id))

    return render_template("garantia_detalle.html", g=g,
                           check_items=GARANTIA_CHECK, estados=_checklist_estados(g))

def _checklist_estados(g):
    """Devuelve el checklist como dict {item: 'ok'|'falla'}, tolerando el formato viejo (lista)."""
    data = json.loads(g.checklist_json) if g.checklist_json else {}
    if isinstance(data, list):
        return {x: "ok" for x in data}
    return data

@app.route("/garantias/<int:gid>/remision")
@rol_required("ADMIN", "TECNICO")
def remision_garantia(gid):
    g = Garantia.query.get_or_404(gid)
    if not g.visita_realizada:
        flash("La remisión técnica se emite al cerrar la visita.", "error")
        return redirect(url_for("garantia_detalle", gid=g.id))
    return render_template("remision_garantia.html", g=g,
                           check_items=GARANTIA_CHECK, estados=_checklist_estados(g))


# ----------------- ADMIN: USUARIOS -----------------
def _admin_verificado():
    """La re-autenticación del admin es válida por 5 minutos."""
    ts = session.get("admin_verif")
    if not ts:
        return False
    return (datetime.utcnow().timestamp() - ts) < 300

@app.route("/usuarios/verificar", methods=["GET", "POST"])
@rol_required("ADMIN")
def usuarios_verificar():
    if request.method == "POST":
        u = Usuario.query.get(session["uid"])
        if u and u.check_password(request.form.get("password", "")):
            session["admin_verif"] = datetime.utcnow().timestamp()
            return redirect(url_for("usuarios"))
        flash("Contraseña incorrecta. Verifica tu identidad para continuar.", "error")
    return render_template("usuarios_verificar.html")

@app.route("/usuarios")
@rol_required("ADMIN")
def usuarios():
    # apartado sensible: exige re-autenticación reciente del admin
    if not _admin_verificado():
        return redirect(url_for("usuarios_verificar"))
    items = Usuario.query.order_by(Usuario.id).all()
    return render_template("usuarios.html", items=items)

@app.route("/usuarios/nuevo", methods=["GET", "POST"])
@rol_required("ADMIN")
def usuario_nuevo():
    if not _admin_verificado():
        return redirect(url_for("usuarios_verificar"))
    if request.method == "POST":
        if Usuario.query.filter_by(correo=request.form["correo"].strip().lower()).first():
            flash("Ya existe un usuario con ese correo.", "error")
        else:
            u = Usuario(nombre=request.form["nombre"].strip(),
                        correo=request.form["correo"].strip().lower(),
                        rol=request.form["rol"])
            u.set_password(request.form["password"])
            db.session.add(u)
            db.session.commit()
            flash("Usuario creado.", "ok")
            return redirect(url_for("usuarios"))
    return render_template("usuario_form.html")


# ----------------- CAPACITACIONES (CAPACITADOR / ADMIN) -----------------
@app.route("/capacitaciones")
@rol_required("ADMIN", "CAPACITADOR")
def capacitaciones():
    items = Capacitacion.query.order_by(Capacitacion.id.desc()).all()
    pendientes = [c for c in items if c.estado == "ABIERTA"]
    realizadas = [c for c in items if c.estado == "CERRADA"]
    return render_template("capacitaciones.html",
                           pendientes=pendientes, realizadas=realizadas, total=len(items))

@app.route("/capacitaciones/archivo")
@rol_required("ADMIN", "CAPACITADOR")
def capacitaciones_archivo():
    realizadas = Capacitacion.query.filter_by(estado="CERRADA")\
        .order_by(Capacitacion.fecha_cierre.desc()).all()
    return render_template("capacitaciones_archivo.html", items=realizadas)

@app.route("/capacitaciones/nueva", methods=["GET", "POST"])
@rol_required("ADMIN", "CAPACITADOR")
def capacitacion_nueva():
    if request.method == "POST":
        f = request.form
        fecha = None
        if f.get("fecha"):
            try:
                fecha = datetime.strptime(f["fecha"], "%Y-%m-%d").date()
            except ValueError:
                fecha = None
        # El título viene de una lista; si eligen "Otro", se toma el texto escrito.
        titulo_sel = f.get("titulo_sel", "").strip()
        if titulo_sel == "__otro__":
            titulo = f.get("titulo_otro", "").strip()
        else:
            titulo = titulo_sel
        c = Capacitacion(
            codigo=generar_codigo_capacitacion(),
            titulo=titulo,
            descripcion=f.get("descripcion", "").strip(),
            capacitador=f.get("capacitador", "").strip() or session.get("nombre"),
            lugar=f.get("lugar", "").strip(),
            modalidad=f.get("modalidad", "PRESENCIAL"),
            fecha=fecha,
            hora=f.get("hora", "").strip(),
            duracion_est=f.get("duracion_est", "").strip(),
            num_esperados=int(f.get("num_esperados") or 0),
            token=Capacitacion.nuevo_token(),
            capacitador_id=session["uid"],
        )
        db.session.add(c)
        db.session.commit()
        flash(f"Capacitación {c.codigo} creada. Comparte el link de firma.", "ok")
        return redirect(url_for("capacitacion_detalle", cid=c.id))
    return render_template("capacitacion_form.html")

@app.route("/capacitaciones/<int:cid>", methods=["GET", "POST"])
@rol_required("ADMIN", "CAPACITADOR")
def capacitacion_detalle(cid):
    c = Capacitacion.query.get_or_404(cid)
    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "subir_foto":
            foto = request.form.get("foto", "")
            if foto:
                db.session.add(FotoCapacitacion(capacitacion_id=c.id, foto=foto))
                db.session.commit()
                flash("Evidencia agregada.", "ok")

        elif accion == "borrar_foto":
            ft = FotoCapacitacion.query.get(int(request.form["foto_id"]))
            if ft and ft.capacitacion_id == c.id:
                db.session.delete(ft); db.session.commit()
                flash("Evidencia eliminada.", "ok")

        elif accion == "firmar_capacitador":
            firma = request.form.get("firma_capacitador", "")
            if firma and len(firma) > 100:
                c.firma_capacitador = firma
                cargo = request.form.get("cargo_capacitador", "").strip()
                doc = request.form.get("doc_capacitador", "").strip()
                c.datos_capacitador = (cargo + " · " + doc).strip(" ·") if (cargo or doc) else ""
                db.session.commit()
                flash("Firma del capacitador guardada.", "ok")
            else:
                flash("La firma del capacitador es obligatoria.", "error")

        elif accion == "cerrar":
            faltan = []
            if c.firmados == 0:
                faltan.append("al menos una firma de asistente")
            if not c.firma_capacitador:
                faltan.append("firma del capacitador")
            if FotoCapacitacion.query.filter_by(capacitacion_id=c.id).count() == 0:
                faltan.append("al menos una foto de evidencia")
            if faltan:
                flash("Para cerrar y emitir el acta falta: " + ", ".join(faltan) + ".", "error")
            else:
                c.duracion_real = request.form.get("duracion_real", "").strip()
                c.estado = "CERRADA"
                c.fecha_cierre = datetime.utcnow()
                c.acta = generar_acta()
                db.session.commit()
                flash(f"Capacitación cerrada. Acta {c.acta} generada.", "ok")
                return redirect(url_for("acta_capacitacion", cid=c.id))

        return redirect(url_for("capacitacion_detalle", cid=c.id))

    link = url_for("firmar_capacitacion", token=c.token, _external=True)
    return render_template("capacitacion_detalle.html", c=c, link=link)

@app.route("/capacitaciones/<int:cid>/acta")
@rol_required("ADMIN", "CAPACITADOR")
def acta_capacitacion(cid):
    c = Capacitacion.query.get_or_404(cid)
    if c.estado != "CERRADA":
        flash("El acta se genera al cerrar la capacitación.", "error")
        return redirect(url_for("capacitacion_detalle", cid=c.id))
    return render_template("acta_capacitacion.html", c=c)

# ----- LINK PÚBLICO de firma (sin login) -----
@app.route("/firmar/<token>", methods=["GET", "POST"])
def firmar_capacitacion(token):
    c = Capacitacion.query.filter_by(token=token).first_or_404()
    if c.estado == "CERRADA":
        return render_template("firmar_publico.html", c=c, cerrada=True)
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        firma = request.form.get("firma", "")
        if nombre and firma and len(firma) > 100:
            db.session.add(AsistenteFirma(
                capacitacion_id=c.id, nombre=nombre,
                documento=request.form.get("documento", "").strip(), firma=firma))
            db.session.commit()
            return render_template("firmar_publico.html", c=c, ok=True)
        return render_template("firmar_publico.html", c=c,
                               error="Escribe tu nombre y firma para registrar tu asistencia.")
    return render_template("firmar_publico.html", c=c)

# QR del link (SVG) — usa el mismo generador de barras no, uno de QR simple
@app.route("/capacitaciones/<int:cid>/qr.svg")
@rol_required("ADMIN", "CAPACITADOR")
def capacitacion_qr(cid):
    c = Capacitacion.query.get_or_404(cid)
    link = url_for("firmar_capacitacion", token=c.token, _external=True)
    import qr_simple
    return Response(qr_simple.qr_svg(link), mimetype="image/svg+xml")


# Al importarse en la nube (gunicorn), preparar la base de datos automáticamente.
# En local esto no estorba: si las tablas ya existen, no hace nada.
if os.environ.get("MYSQL_URL") or os.environ.get("DATABASE_URL"):
    inicializar_datos()

if __name__ == "__main__":
    # En local: puerto 8080. En la nube: el puerto que indique la variable PORT.
    puerto = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", debug=False, port=puerto, use_reloader=False)
