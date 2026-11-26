"""AVACOM — Lógica de negocio: SKU, radicados, movimientos."""
from datetime import datetime
from models import db, Producto, Categoria, Movimiento, Garantia, Despacho

def generar_sku(categoria):
    """Genera un SKU único: AVC-<PREFIJO>-<consecutivo 5 dígitos>."""
    base = f"AVC-{categoria.prefijo}-"
    # contar productos existentes de esa categoría
    n = Producto.query.filter_by(categoria_id=categoria.id).count() + 1
    sku = f"{base}{n:05d}"
    # asegurar unicidad por si acaso
    while Producto.query.filter_by(sku=sku).first():
        n += 1
        sku = f"{base}{n:05d}"
    return sku

def generar_radicado():
    n = Garantia.query.count() + 1
    rad = f"GAR-{n:05d}"
    while Garantia.query.filter_by(radicado=rad).first():
        n += 1
        rad = f"GAR-{n:05d}"
    return rad

# ---- Código de barras (Code128-B) como SVG, sin librerías externas ----
_C128B = [
 "11011001100","11001101100","11001100110","10010011000","10010001100","10001001100",
 "10011001000","10011000100","10001100100","11001001000","11001000100","11000100100",
 "10110011100","10011011100","10011001110","10111001100","10011101100","10011100110",
 "11001110010","11001011100","11001001110","11011100100","11001110100","11101101110",
 "11101001100","11100101100","11100100110","11101100100","11100110100","11100110010",
 "11011011000","11011000110","11000110110","10100011000","10001011000","10001000110",
 "10110001000","10001101000","10001100010","11010001000","11000101000","11000100010",
 "10110111000","10110001110","10001101110","10111011000","10111000110","10001110110",
 "11101110110","11010001110","11000101110","11011101000","11011100010","11011101110",
 "11101011000","11101000110","11100010110","11101101000","11101100010","11100011010",
 "11101111010","11001000010","11110001010","10100110000","10100001100","10010110000",
 "10010000110","10000101100","10000100110","10110010000","10110000100","10011010000",
 "10011000010","10000110100","10000110010","11000010010","11001010000","11110111010",
 "11000010100","10001111010","10100111100","10010111100","10010011110","10111100100",
 "10011110100","10011110010","11110100100","11110010100","11110010010","11011011110",
 "11011110110","11110110110","10101111000","10100011110","10001011110","10111101000",
 "10111100010","11110101000","11110100010","10111011110","10111101110","11101011110",
 "11110101110","11010000100","11010010000","11010011100","11000111010"]
_START_B = 104; _STOP = "1100011101011"

def codigo_barras_svg(texto, h=70, unidad=2):
    """Devuelve un SVG Code128-B del texto dado."""
    vals = [_START_B] + [ord(c)-32 for c in texto if 32 <= ord(c) <= 126]
    checksum = (vals[0] + sum(i*v for i, v in enumerate(vals[1:], start=1))) % 103
    patron = "".join(_C128B[v] for v in vals) + _C128B[checksum] + _STOP
    x = 0; rects = []
    for i, bit in enumerate(patron):
        if bit == "1":
            rects.append(f'<rect x="{x}" y="0" width="{unidad}" height="{h}" fill="#1A1A1E"/>')
        x += unidad
    w = len(patron) * unidad
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">{"".join(rects)}</svg>')
    """Registra entrada/salida y actualiza stock. Devuelve (ok, mensaje)."""
    cantidad = int(cantidad)
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor a cero."
    if tipo == "SALIDA" and cantidad > producto.stock:
        return False, f"Stock insuficiente. Disponible: {producto.stock}."
    producto.stock += cantidad if tipo == "ENTRADA" else -cantidad
    mov = Movimiento(tipo=tipo, producto_id=producto.id, cantidad=cantidad, usuario_id=usuario_id)
    db.session.add(mov)
    db.session.commit()
    return True, "Movimiento registrado."


def generar_remision():
    n = Despacho.query.filter(Despacho.remision.isnot(None)).count() + 1
    rem = f"REM-{n:05d}"
    while Despacho.query.filter_by(remision=rem).first():
        n += 1
        rem = f"REM-{n:05d}"
    return rem


def generar_remision_tecnica():
    """Consecutivo de la remisión de visita/gestión técnica: REM-TEC-00001."""
    n = Garantia.query.filter(Garantia.remision_tecnica.isnot(None)).count() + 1
    rem = f"REM-TEC-{n:05d}"
    while Garantia.query.filter_by(remision_tecnica=rem).first():
        n += 1
        rem = f"REM-TEC-{n:05d}"
    return rem


def generar_codigo_capacitacion():
    from models import Capacitacion
    n = Capacitacion.query.count() + 1
    cod = f"CAP-{n:05d}"
    while Capacitacion.query.filter_by(codigo=cod).first():
        n += 1
        cod = f"CAP-{n:05d}"
    return cod


def generar_acta():
    from models import Capacitacion
    n = Capacitacion.query.filter(Capacitacion.acta.isnot(None)).count() + 1
    acta = f"ACTA-{n:05d}"
    while Capacitacion.query.filter_by(acta=acta).first():
        n += 1
        acta = f"ACTA-{n:05d}"
    return acta


def registrar_movimiento(producto, tipo, cantidad, usuario_id,
                          responsable=None, motivo=None, firma=None):
    """Registra entrada/salida y actualiza stock. Devuelve (ok, mensaje)."""
    cantidad = int(cantidad)
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor a cero."
    if tipo == "SALIDA" and cantidad > producto.stock:
        return False, f"Stock insuficiente. Disponible: {producto.stock}."
    producto.stock += cantidad if tipo == "ENTRADA" else -cantidad
    mov = Movimiento(tipo=tipo, producto_id=producto.id, cantidad=cantidad,
                     usuario_id=usuario_id, responsable=responsable,
                     motivo=motivo, firma=firma)
    db.session.add(mov)
    db.session.commit()
    return True, "Movimiento registrado."
