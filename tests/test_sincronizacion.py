import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conectores.base import ErrorConector, Registro
from app.models import Documento, Trozo
from app.services import catalogo
from app.services.sincronizacion import ResumenSincronizacion, sincronizar_coleccion
from tests.dobles import proveedor_doble


class ConectorDoble:
    nombre = "doble"

    def __init__(self, registros: list[Registro]) -> None:
        self.actuales = registros
        self.caido = False

    def registros(self) -> list[Registro]:
        if self.caido:
            raise ErrorConector("La fuente no respondió")
        return self.actuales


def _registro(id_externo: str, texto: str) -> Registro:
    return Registro(id_externo=id_externo, titulo=f"resume: {id_externo}", texto=texto)


TRABAJO = _registro("work:SIIGSA", "Sección: work\nsummary: Riego del olivo en el SAG")
PROYECTO = _registro("projects:biblioteca-rag", "Sección: projects\ndescription: Poda con cita")
HABILIDAD = _registro("skills:Backend", "Sección: skills\nkeywords: Python, FastAPI, cosecha")


@pytest.fixture(autouse=True)
def coleccion(db: Session) -> None:
    catalogo.crear_espacio(db, "personal", "Personal")
    catalogo.crear_coleccion(db, "personal", "sobre-mi", "Sobre mí")


def _sincronizar(db: Session, conector: ConectorDoble) -> ResumenSincronizacion:
    return sincronizar_coleccion(db, "personal", "sobre-mi", conector, proveedor_doble())


def _documentos(db: Session) -> dict[str, Documento]:
    return {d.id_externo: d for d in db.scalars(select(Documento)) if d.id_externo}


def test_primera_sincronizacion_ingiere_cada_registro(db: Session) -> None:
    resumen = _sincronizar(db, ConectorDoble([TRABAJO, PROYECTO, HABILIDAD]))

    assert (resumen.nuevos, resumen.sin_cambios, resumen.eliminados) == (3, 0, 0)
    documentos = _documentos(db)
    assert set(documentos) == {"work:SIIGSA", "projects:biblioteca-rag", "skills:Backend"}
    assert documentos["work:SIIGSA"].nombre_archivo == "resume: work:SIIGSA"


def test_sin_cambios_en_la_fuente_no_toca_nada(db: Session) -> None:
    conector = ConectorDoble([TRABAJO, PROYECTO])
    _sincronizar(db, conector)
    ids_antes = {d.id for d in _documentos(db).values()}

    resumen = _sincronizar(db, conector)

    assert (resumen.nuevos, resumen.actualizados, resumen.sin_cambios) == (0, 0, 2)
    assert {d.id for d in _documentos(db).values()} == ids_antes


def test_refleja_cambios_altas_y_bajas_de_la_fuente(db: Session) -> None:
    conector = ConectorDoble([TRABAJO, PROYECTO])
    _sincronizar(db, conector)
    cambiado = _registro("work:SIIGSA", "Sección: work\nsummary: Fertilizacion con potasio")
    conector.actuales = [cambiado, HABILIDAD]  # PROYECTO desaparece, HABILIDAD es nueva

    resumen = _sincronizar(db, conector)

    resumen_tupla = (resumen.nuevos, resumen.actualizados, resumen.sin_cambios, resumen.eliminados)
    assert resumen_tupla == (1, 1, 0, 1)
    documentos = _documentos(db)
    assert set(documentos) == {"work:SIIGSA", "skills:Backend"}
    textos = [
        t.texto
        for t in db.scalars(select(Trozo).where(Trozo.documento_id == documentos["work:SIIGSA"].id))
    ]
    assert any("potasio" in texto for texto in textos)
    assert not any("olivo" in texto for texto in textos)  # el trozo viejo ya no está


def test_fuente_caida_no_borra_lo_que_ya_estaba(db: Session) -> None:
    conector = ConectorDoble([TRABAJO, PROYECTO])
    _sincronizar(db, conector)
    conector.caido = True

    with pytest.raises(ErrorConector):
        _sincronizar(db, conector)

    assert set(_documentos(db)) == {"work:SIIGSA", "projects:biblioteca-rag"}


def test_fuente_vacia_con_documentos_es_error_y_no_borra_nada(db: Session) -> None:
    """C1: una respuesta 200 vacía no puede vaciar la colección por accidente."""
    conector = ConectorDoble([TRABAJO, PROYECTO])
    _sincronizar(db, conector)
    conector.actuales = []

    with pytest.raises(ErrorConector, match="0 registros"):
        _sincronizar(db, conector)

    assert set(_documentos(db)) == {"work:SIIGSA", "projects:biblioteca-rag"}


def test_vaciar_la_coleccion_exige_pedirlo_explicitamente(db: Session) -> None:
    conector = ConectorDoble([TRABAJO, PROYECTO])
    _sincronizar(db, conector)
    conector.actuales = []

    resumen = sincronizar_coleccion(
        db, "personal", "sobre-mi", conector, proveedor_doble(), permitir_vaciar=True
    )

    assert resumen.eliminados == 2
    assert _documentos(db) == {}


def test_ids_repetidos_en_la_fuente_son_error_del_conector(db: Session) -> None:
    """C2: con el mismo id, el segundo registro se contaba «sin cambios» y nunca se indexaba."""
    otro_con_mismo_id = _registro("work:SIIGSA", "Sección: work\nsummary: Otro cargo")

    with pytest.raises(ErrorConector, match="work:SIIGSA"):
        _sincronizar(db, ConectorDoble([TRABAJO, otro_con_mismo_id]))

    assert _documentos(db) == {}


def test_una_sola_clasificacion_para_cada_caso(db: Session) -> None:
    """C2: el resumen y el trabajo cuentan igual un texto repetido y un registro sin cambios."""
    from app.services.ingesta_por_lotes import Resultado

    texto_repetido = _registro("projects:copia", TRABAJO.texto)
    conector = ConectorDoble([TRABAJO, texto_repetido])
    vistos: list[Resultado] = []

    primera = sincronizar_coleccion(
        db,
        "personal",
        "sobre-mi",
        conector,
        proveedor_doble(),
        contar=lambda _db, archivo: vistos.append(archivo.resultado),
    )
    conector.actuales = [TRABAJO]
    segunda = sincronizar_coleccion(
        db,
        "personal",
        "sobre-mi",
        conector,
        proveedor_doble(),
        contar=lambda _db, archivo: vistos.append(archivo.resultado),
    )

    assert (primera.nuevos, primera.duplicados) == (1, 1)
    assert segunda.sin_cambios == 1
    assert vistos == [Resultado.INGERIDO, Resultado.DUPLICADO, Resultado.SIN_CAMBIOS]
