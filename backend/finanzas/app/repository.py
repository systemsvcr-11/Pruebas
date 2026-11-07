
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from .database import engine
from .config import settings


# ============================================================
# DATOS DE DEMOSTRACIÓN
# Se conservan para cuando DATA_SOURCE no sea "azure".
# ============================================================
FECHA_DESDE = "2026-10-12"

DEMO_INVOICES = [
    {
        "id": 1, "fecha": "2026-10-12",
        "empresa": "Empresa Demo",
        "proveedor": "Proveedor Norte",
        "producto_codigo": "P001", "producto_nombre": "Aceite vegetal",
        "cantidad": 50, "unidad": "L", "precio_unitario": 12.0,
        "total_linea": 600.0, "numero_factura": "F001-254",
    },
    {
        "id": 2, "fecha": "2026-10-13",
        "empresa": "Empresa Demo",
        "proveedor": "Proveedor Centro",
        "producto_codigo": "P002", "producto_nombre": "Arroz extra",
        "cantidad": 100, "unidad": "kg", "precio_unitario": 4.8,
        "total_linea": 480.0, "numero_factura": "F002-101",
    },
    {
        "id": 3, "fecha": "2026-10-14",
        "empresa": "Empresa Demo",
        "proveedor": "Proveedor Norte",
        "producto_codigo": "P003", "producto_nombre": "Azúcar",
        "cantidad": 20, "unidad": "kg", "precio_unitario": 5.4,
        "total_linea": 108.0, "numero_factura": "F001-255",
    },
]

DEMO_RECEIPTS = [
    {
        "id": 1, "fecha": "2026-10-12",
        "empresa": "Empresa Demo", "proveedor": "Proveedor Norte",
        "producto_codigo": "P001", "producto_nombre": "Aceite vegetal",
        "cantidad": 45, "unidad": "L",
        "documento_referencia": "OC-001",
    },
    {
        "id": 2, "fecha": "2026-10-13",
        "empresa": "Empresa Demo", "proveedor": "Proveedor Centro",
        "producto_codigo": "P002", "producto_nombre": "Arroz extra",
        "cantidad": 100, "unidad": "kg",
        "documento_referencia": "OC-002",
    },
    {
        "id": 3, "fecha": "2026-10-14",
        "empresa": "Empresa Demo", "proveedor": "Proveedor Norte",
        "producto_codigo": "P003", "producto_nombre": "Azúcar",
        "cantidad": 20, "unidad": "kg",
        "documento_referencia": "OC-003",
    },
]


# ============================================================
# UTILIDADES
# ============================================================

def _rows(sql, params=None):
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result.fetchall()]


def _normalizar(valor):
    """Normaliza texto para comparar nombres, productos y unidades."""
    if valor is None:
        return ""

    valor = unicodedata.normalize("NFKD", str(valor))
    valor = "".join(c for c in valor if not unicodedata.combining(c))
    valor = re.sub(r"\s+", " ", valor.strip())
    return valor.casefold()


def _numero(valor):
    if valor is None:
        return 0.0
    if isinstance(valor, Decimal):
        return float(valor)
    try:
        return float(valor)
    except (ValueError, TypeError):
        return 0.0


def _fecha(valor):
    """Convierte fechas SQL o texto a date; devuelve None si no puede."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    texto = str(valor).strip()
    if not texto:
        return None

    # Formatos comunes de fecha recibidos desde SQL o archivos.
    for formato in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(texto[:19], formato).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _semana_iso(valor):
    fecha = _fecha(valor)
    if fecha is None:
        return None
    iso = fecha.isocalendar()
    return iso.year, iso.week


def _clave_conciliacion(registro):
    """
    La conciliación NO relaciona una factura con una orden individual.
    Compara los acumulados de empresa + año/semana ISO + producto + unidad.
    """
    semana = _semana_iso(registro.get("fecha"))
    if semana is None:
        return None

    return (
        _normalizar(registro.get("empresa")),
        semana[0],
        semana[1],
        _normalizar(registro.get("producto_nombre")),
        _normalizar(registro.get("unidad")),
    )


# ============================================================
# LECTURA DE FACTURAS
# Tabla original: dbo.BD_FACTURAS_LOG
# ============================================================

def get_invoices():
    if settings.data_source.lower() != "azure":
        return DEMO_INVOICES

    sql = """
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY
                    TRY_CONVERT(date, [FECHA EMS]),
                    [N° FAC],
                    [ITEM],
                    [PROVEEDOR]
            ) AS id,
            TRY_CONVERT(date, [FECHA EMS]) AS fecha,
            [RAZON SOCIAL] AS empresa,
            [RUC] AS ruc,
            [PROVEEDOR] AS proveedor,
            [N° FAC] AS numero_factura,
            [ITEM] AS producto_nombre,
            [ITEM] AS producto_codigo,
            [U.M.D] AS unidad,
            TRY_CONVERT(decimal(18, 4), [CANTIDAD]) AS cantidad,
            TRY_CONVERT(decimal(18, 4), [PRECIO C/IGV]) AS precio_unitario,
            TRY_CONVERT(decimal(18, 2), [TOTAL REAL]) AS total_linea,
            TRY_CONVERT(int, [N° SEMANA]) AS semana_origen
        FROM dbo.BD_FACTURAS_LOG
        WHERE TRY_CONVERT(date, [FECHA EMS]) >= :fecha_desde
    """

    rows = _rows(sql, {"fecha_desde": FECHA_DESDE})

    for row in rows:
        fecha = _fecha(row.get("fecha"))
        row["fecha"] = fecha.isoformat() if fecha else None
        row["cantidad"] = _numero(row.get("cantidad"))
        row["precio_unitario"] = _numero(row.get("precio_unitario"))
        row["total_linea"] = _numero(row.get("total_linea"))

        # El nombre del producto se usa como código provisional.
        # No se ha identificado una columna con código de producto.
        row["producto_codigo"] = str(row.get("producto_nombre") or "").strip()
        row["producto_nombre"] = str(row.get("producto_nombre") or "").strip()

    return rows


# ============================================================
# LECTURA DE RECEPCIONES
# Tabla original: dbo.BD_ORDEN_COMPRA_ODOO
# ============================================================

def get_receipts():
    if settings.data_source.lower() != "azure":
        return DEMO_RECEIPTS

    sql = """
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY
                    TRY_CONVERT(date, [Entrega esperada]),
                    [Referencia de la orden],
                    [ITEM],
                    [Proveedor]
            ) AS id,
            TRY_CONVERT(date, [Entrega esperada]) AS fecha,
            [Empresa] AS empresa,
            [Proveedor] AS proveedor,
            [Referencia de la orden] AS documento_referencia,
            [ITEM] AS producto_nombre,
            [ITEM] AS producto_codigo,
            [UNIDAD] AS unidad,
            TRY_CONVERT(decimal(18, 4), [CANTIDAD PROGRAMADA])
                AS cantidad_programada,
            TRY_CONVERT(decimal(18, 4), [CANTIDAD RECIBIDA])
                AS cantidad
        FROM dbo.BD_ORDEN_COMPRA_ODOO
        WHERE TRY_CONVERT(date, [Entrega esperada]) >= :fecha_desde
    """

    rows = _rows(sql, {"fecha_desde": FECHA_DESDE})

    for row in rows:
        fecha = _fecha(row.get("fecha"))
        row["fecha"] = fecha.isoformat() if fecha else None
        row["cantidad"] = _numero(row.get("cantidad"))
        row["cantidad_programada"] = _numero(
            row.get("cantidad_programada")
        )
        row["producto_codigo"] = str(row.get("producto_nombre") or "").strip()
        row["producto_nombre"] = str(row.get("producto_nombre") or "").strip()

    return rows


# ============================================================
# ALERTAS DE CONCILIACIÓN SEMANAL Y PRECIOS
# ============================================================

def get_alerts():
    invoices = get_invoices()
    receipts = get_receipts()

    # --------------------------------------------------------
    # 1. Acumular facturas y recepciones por semana.
    # --------------------------------------------------------

    acumulado = {}

    for inv in invoices:
        key = _clave_conciliacion(inv)
        if key is None:
            continue

        grupo = acumulado.setdefault(key, {
            "empresa": inv.get("empresa") or "",
            "anio": key[1],
            "semana": key[2],
            "producto": inv.get("producto_nombre") or "",
            "unidad": inv.get("unidad") or "",
            "facturado": 0.0,
            "recibido": 0.0,
            "importe_facturado": 0.0,
            "proveedores": set(),
            "facturas": set(),
            "fechas_factura": [],
        })

        grupo["facturado"] += _numero(inv.get("cantidad"))
        grupo["importe_facturado"] += _numero(inv.get("total_linea"))

        if inv.get("proveedor"):
            grupo["proveedores"].add(str(inv["proveedor"]))
        if inv.get("numero_factura"):
            grupo["facturas"].add(str(inv["numero_factura"]))
        if inv.get("fecha"):
            grupo["fechas_factura"].append(str(inv["fecha"])[:10])

    for rec in receipts:
        key = _clave_conciliacion(rec)
        if key is None:
            continue

        grupo = acumulado.setdefault(key, {
            "empresa": rec.get("empresa") or "",
            "anio": key[1],
            "semana": key[2],
            "producto": rec.get("producto_nombre") or "",
            "unidad": rec.get("unidad") or "",
            "facturado": 0.0,
            "recibido": 0.0,
            "importe_facturado": 0.0,
            "proveedores": set(),
            "facturas": set(),
            "fechas_factura": [],
        })

        grupo["recibido"] += _numero(rec.get("cantidad"))

    alerts = []

    # --------------------------------------------------------
    # 2. Alertas de diferencia de cantidades semanales.
    # --------------------------------------------------------

    for key, grupo in acumulado.items():
        facturado = grupo["facturado"]
        recibido = grupo["recibido"]

        # Ignorar grupos sin facturación ni recepción.
        if facturado == 0 and recibido == 0:
            continue
        
        diferencia = facturado - recibido

        if abs(diferencia) <= 0.00001:
            continue

        # Estimación del valor de la diferencia usando el precio
        # medio ponderado de las líneas facturadas del grupo.
        precio_medio = (
            grupo["importe_facturado"] / facturado
            if facturado > 0
            else 0.0
        )

        fechas = grupo["fechas_factura"]
        fecha_alerta = max(fechas) if fechas else ""

        alerts.append({
            "id": (
                f"QTY-{key[1]}-{key[2]}-"
                f"{abs(hash(key))}"
            ),
            "type": "Diferencia semanal de cantidad",
            "severity": "high" if diferencia > 0 else "medium",
            "company": grupo["empresa"],
            "year": grupo["anio"],
            "week": grupo["semana"],
            "product": grupo["producto"],
            "supplier": ", ".join(sorted(grupo["proveedores"])),
            "message": (
                f"Semana {grupo['semana']} de {grupo['anio']} — "
                f"facturado: {facturado:g} {grupo['unidad']}; "
                f"recibido: {recibido:g} {grupo['unidad']}; "
                f"diferencia: {diferencia:+g} {grupo['unidad']}."
            ),
            "quantity_invoiced": round(facturado, 4),
            "quantity_received": round(recibido, 4),
            "quantity_difference": round(diferencia, 4),
            "invoice_count": len(grupo["facturas"]),
            "amount": round(max(diferencia, 0) * precio_medio, 2),
            "status": "Pendiente",
            "date": fecha_alerta,
        })

    # --------------------------------------------------------
    # 3. Alertas de aumento de precio.
    # Se utiliza PRECIO C/IGV y se compara por empresa,
    # proveedor y producto.
    # --------------------------------------------------------

    historial = {}

    for inv in invoices:
        fecha = _fecha(inv.get("fecha"))
        precio = _numero(inv.get("precio_unitario"))

        if fecha is None or precio <= 0:
            continue

        clave = (
            _normalizar(inv.get("empresa")),
            _normalizar(inv.get("proveedor")),
            _normalizar(inv.get("producto_nombre")),
        )

        historial.setdefault(clave, []).append(inv)

    for clave, history in historial.items():
        history.sort(key=lambda row: str(row.get("fecha") or ""))

        # Conserva la última observación por fecha, para evitar
        # comparar dos líneas de la misma factura/fecha como si
        # fueran necesariamente un cambio temporal.
        por_fecha = {}
        for row in history:
            por_fecha[str(row.get("fecha") or "")[:10]] = row

        history = [
            por_fecha[fecha]
            for fecha in sorted(por_fecha)
            if fecha
        ]

        if len(history) < 2:
            continue

        oldrow, newrow = history[-2], history[-1]
        old = _numero(oldrow.get("precio_unitario"))
        new = _numero(newrow.get("precio_unitario"))

        if old <= 0:
            continue

        variacion = (new - old) / old

        if variacion < 0.05:
            continue

        porcentaje = variacion * 100
        empresa = newrow.get("empresa") or ""
        proveedor = newrow.get("proveedor") or ""
        producto = newrow.get("producto_nombre") or ""

        alerts.append({
            "id": f"PRICE-{newrow.get('id')}",
            "type": "Aumento de precio",
            "severity": "medium",
            "company": empresa,
            "product": producto,
            "supplier": proveedor,
            "message": (
                f"Precio con IGV pasó de {old:.2f} a {new:.2f} "
                f"(+{porcentaje:.1f}%)."
            ),
            "amount": round(
                (new - old) * _numero(newrow.get("cantidad")), 2
            ),
            "status": "Pendiente",
            "date": str(newrow.get("fecha") or "")[:10],
        })

    return alerts
