"""PDF válido mínimo, generado en el test: los PDF del corpus tienen licencia sin revisar y no se
copian al repo. Una página con texto vacío queda sin capa de texto (simula una escaneada)."""

ALTO_PAGINA = 792
ANCHO_PAGINA = 612
MARGEN = 72
INTERLINEADO = 16
TAMANO_FUENTE = 11


def pdf_minimo(paginas: list[str]) -> bytes:
    """Cada elemento es el texto de una página (ASCII); las líneas se separan con `\\n`."""
    numero_paginas = len(paginas)
    primer_objeto_pagina = 4
    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _arbol_paginas(numero_paginas, primer_objeto_pagina),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for indice in range(numero_paginas):
        objeto_contenido = primer_objeto_pagina + numero_paginas + indice
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO_PAGINA} {ALTO_PAGINA}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {objeto_contenido} 0 R >>".encode()
        )
    for texto in paginas:
        flujo = _flujo_de_texto(texto)
        objetos.append(b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream")
    return _serializar(objetos)


def _arbol_paginas(numero_paginas: int, primer_objeto_pagina: int) -> bytes:
    hijos = " ".join(f"{primer_objeto_pagina + i} 0 R" for i in range(numero_paginas))
    return f"<< /Type /Pages /Kids [{hijos}] /Count {numero_paginas} >>".encode()


def _flujo_de_texto(texto: str) -> bytes:
    if not texto:
        return b""
    lineas = [
        f"({_escapar(linea)}) Tj 0 -{INTERLINEADO} Td" for linea in texto.splitlines() if linea
    ]
    cuerpo = " ".join(lineas)
    inicio_y = ALTO_PAGINA - MARGEN
    return f"BT /F1 {TAMANO_FUENTE} Tf {MARGEN} {inicio_y} Td {cuerpo} ET".encode("ascii")


def _escapar(linea: str) -> str:
    return linea.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _serializar(objetos: list[bytes]) -> bytes:
    salida = bytearray(b"%PDF-1.4\n")
    desplazamientos: list[int] = []
    for numero, cuerpo in enumerate(objetos, start=1):
        desplazamientos.append(len(salida))
        salida += b"%d 0 obj\n" % numero + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for desplazamiento in desplazamientos:
        salida += b"%010d 00000 n \n" % desplazamiento
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objetos) + 1)
    salida += b"startxref\n%d\n%%%%EOF\n" % inicio_xref
    return bytes(salida)
