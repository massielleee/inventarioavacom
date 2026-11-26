"""Genera un código QR como SVG a partir de un texto/URL.

Usa la librería 'qrcode' solo para calcular la matriz de módulos
(el algoritmo QR real), y dibuja el SVG a mano para no depender de Pillow.
"""
import qrcode


def qr_svg(texto, escala=8, borde=4):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=borde,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    matriz = qr.get_matrix()           # lista de listas de bool
    n = len(matriz)
    lado = n * escala
    rects = []
    for y, fila in enumerate(matriz):
        for x, celda in enumerate(fila):
            if celda:
                rects.append(
                    f'<rect x="{x*escala}" y="{y*escala}" '
                    f'width="{escala}" height="{escala}"/>'
                )
    cuerpo = "".join(rects)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lado}" height="{lado}" '
        f'viewBox="0 0 {lado} {lado}" shape-rendering="crispEdges">'
        f'<rect width="{lado}" height="{lado}" fill="#fff"/>'
        f'<g fill="#1A1A1E">{cuerpo}</g></svg>'
    )
