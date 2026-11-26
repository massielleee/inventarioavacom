"""AVACOM — Crea las tablas y carga datos de ejemplo."""
from app import app
from models import db, Usuario, Categoria, Marca, Producto, Garantia, Despacho
from servicios import generar_sku, generar_radicado, registrar_movimiento

def seed():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # --- Usuarios (uno por rol) ---
        admin = Usuario(nombre="Massielle Julio", correo="admin@avacom.co", rol="ADMIN")
        admin.set_password("admin123")
        bod = Usuario(nombre="Carlos Bodega", correo="bodega@avacom.co", rol="BODEGA")
        bod.set_password("bodega123")
        tec = Usuario(nombre="Laura Técnica", correo="tecnico@avacom.co", rol="TECNICO")
        tec.set_password("tecnico123")
        cap = Usuario(nombre="Andrés Capacitador", correo="capacitador@avacom.co", rol="CAPACITADOR")
        cap.set_password("capacita123")
        db.session.add_all([admin, bod, tec, cap])
        db.session.commit()

        # --- Categorías de ecosistemas educativos (prefijo para SKU) ---
        cats = {}
        for nom, pref in [("Tableros inteligentes", "TABL"),
                          ("Tablets educativas", "TBLT"),
                          ("Mesas interactivas", "MESA"),
                          ("Accesorios", "ACCE")]:
            c = Categoria(nombre=nom, prefijo=pref)
            db.session.add(c); cats[nom] = c
        # Marca interna AVACOM (todo es marca AVACOM)
        marca = Marca(nombre="AVACOM"); db.session.add(marca)
        db.session.commit()

        # --- Productos del catálogo educativo, con SKU automático ---
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

        # --- Una garantía de ejemplo ---
        g = Garantia(radicado=generar_radicado(), producto_id=prods[0].id,
                     cliente="Colegio San José", telefono="3101234567",
                     descripcion="El tablero no registra el táctil en el borde derecho.",
                     motivo_dano="Golpe durante instalación",
                     quien_llamo="Coord. Diana Páez", origen_llamada="Sede Norte - Bogotá",
                     tipo_soporte="PRESENCIAL",
                     estado="EN_REVISION", requiere_visita=True, tecnico_id=tec.id)
        db.session.add(g); db.session.commit()

        print("Base de datos creada con datos de ejemplo.")
        print("Usuarios:")
        print("  Admin   -> admin@avacom.co / admin123")
        print("  Bodega  -> bodega@avacom.co / bodega123")
        print("  Técnico -> tecnico@avacom.co / tecnico123")
        print("  Capacitador -> capacitador@avacom.co / capacita123")

if __name__ == "__main__":
    seed()
