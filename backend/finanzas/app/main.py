from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import settings
from .database import engine
from .repository import get_invoices, get_receipts, get_alerts

import re
import unicodedata
from datetime import date, datetime

app = FastAPI(title=settings.app_name, version="0.1.0")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                   allow_methods=["GET", "PATCH"], allow_headers=["*"])

if settings.data_source.lower() != "azure":
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alert_status (alert_id TEXT PRIMARY KEY, status TEXT NOT NULL, comment TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"))

@app.get("/api/health")
def health():
    return {"status": "ok", "data_source": settings.data_source}

@app.get("/api/dashboard/resumen")
def dashboard_summary():
    invoices, receipts, alerts = get_invoices(), get_receipts(), get_alerts()
    return {"total_facturado": round(sum(float(x.get("total_linea") or 0) for x in invoices), 2),
            "lineas_factura": len(invoices), "lineas_recepcion": len(receipts),
            "alertas_pendientes": len(alerts),
            "importe_observado": round(sum(float(a["amount"]) for a in alerts), 2),
            "alertas": alerts[:8]}

def _normalizar_clave(valor):
    texto = str(valor or "").strip().casefold()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", texto)


def _obtener_periodo(fecha):
    if not fecha:
        return None

    if isinstance(fecha, datetime):
        fecha = fecha.date()

    if isinstance(fecha, date):
        f = fecha
    else:
        try:
            f = date.fromisoformat(str(fecha)[:10])
        except (ValueError, TypeError):
            return None

    anio, semana, _ = f.isocalendar()
    return anio, semana


@app.get("/api/conciliaciones")
def conciliations():
    invoices = get_invoices()
    receipts = get_receipts()

    grupos = {}

    def clave(fila):
        periodo = _obtener_periodo(fila.get("fecha"))
        if periodo is None:
            return None

        empresa = _normalizar_clave(fila.get("empresa"))
        producto = _normalizar_clave(
            fila.get("producto_nombre")
            or fila.get("producto_codigo")
        )
        unidad = _normalizar_clave(fila.get("unidad"))

        return (
            empresa,
            periodo[0],
            periodo[1],
            producto,
            unidad,
        )

    # Acumular las cantidades facturadas por semana y producto.
    for inv in invoices:
        k = clave(inv)
        if k is None:
            continue

        grupo = grupos.setdefault(k, {
            "empresa": inv.get("empresa") or "",
            "anio": k[1],
            "semana": k[2],
            "producto": (
                inv.get("producto_nombre")
                or inv.get("producto_codigo")
                or ""
            ),
            "producto_codigo": inv.get("producto_codigo") or "",
            "unidad": inv.get("unidad") or "",
            "cantidad_facturada": 0.0,
            "cantidad_recibida": 0.0,
            "total_facturado": 0.0,
            "facturas": [],
        })

        cantidad = float(inv.get("cantidad") or 0)
        total = float(inv.get("total_linea") or 0)

        grupo["cantidad_facturada"] += cantidad
        grupo["total_facturado"] += total

        # Conservar el detalle de cada línea de factura.
        grupo["facturas"].append({
            "id": inv.get("id"),
            "fecha": str(inv.get("fecha") or "")[:10],
            "factura": inv.get("numero_factura") or "",
            "proveedor": inv.get("proveedor") or "",
            "cantidad": cantidad,
            "precio_unitario": float(
                inv.get("precio_unitario") or 0
            ),
            "total_linea": total,
        })

    # Acumular las cantidades recibidas por la misma clave.
    for rec in receipts:
        k = clave(rec)
        if k is None:
            continue

        grupo = grupos.setdefault(k, {
            "empresa": rec.get("empresa") or "",
            "anio": k[1],
            "semana": k[2],
            "producto": (
                rec.get("producto_nombre")
                or rec.get("producto_codigo")
                or ""
            ),
            "producto_codigo": rec.get("producto_codigo") or "",
            "unidad": rec.get("unidad") or "",
            "cantidad_facturada": 0.0,
            "cantidad_recibida": 0.0,
            "total_facturado": 0.0,
            "facturas": [],
        })

        grupo["cantidad_recibida"] += float(
            rec.get("cantidad") or 0
        )

    # Preparar la respuesta del dashboard.
    resultado = []
  
    for grupo in grupos.values():
        facturada = grupo["cantidad_facturada"]
        recibida = grupo["cantidad_recibida"]
    
        # Omitir productos sin cantidad facturada ni recibida.
        if abs(facturada) <= 0.00001 and abs(recibida) <= 0.00001:
            continue
    
        diferencia = round(facturada - recibida, 4)

        grupo["periodo"] = (
            f'{grupo["anio"]}-S{grupo["semana"]:02d}'
        )
        grupo["diferencia"] = diferencia
        precio_promedio = (
            grupo["total_facturado"] / facturada
            if facturada > 0
            else 0
        )

        grupo["importe_diferencia"] = round(
            max(diferencia, 0) * precio_promedio, 2
        )

        # Identificador legible y estable entre reinicios.
        grupo["id"] = (
            f'{grupo["anio"]}-S{grupo["semana"]:02d}-'
            f'{grupo["empresa"]}-'
            f'{grupo["producto"]}-'
            f'{grupo["unidad"]}'
        )

        grupo["facturas"].sort(
            key=lambda f: (f["fecha"], f["factura"])
        )
        resultado.append(grupo)

    resultado.sort(
        key=lambda x: (
            x["anio"],
            x["semana"],
            x["empresa"],
            x["producto"],
        ),
        reverse=True,
    )

    return resultado

@app.get("/api/alertas")
def list_alerts(status: str | None = Query(default=None)):
    alerts = get_alerts()
    if settings.data_source.lower() != "azure":
        with engine.connect() as conn:
            statuses = {r[0]: (r[1], r[2]) for r in conn.execute(text("SELECT alert_id,status,comment FROM alert_status")).fetchall()}
        for a in alerts:
            if a["id"] in statuses:
                a["status"] = statuses[a["id"]][0]
                if statuses[a["id"]][1]:
                    a["message"] += " | Nota: " + statuses[a["id"]][1]
    return [a for a in alerts if not status or a["status"].lower() == status.lower()]

@app.patch("/api/alertas/{alert_id}")
def update_alert(alert_id: str, payload: dict):
    allowed = {"Pendiente", "En revisión", "Justificada", "Reclamo enviado", "Resuelta"}
    status = payload.get("status")
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Usa: {', '.join(sorted(allowed))}")
    if settings.data_source.lower() == "azure":
        raise HTTPException(status_code=501, detail="Antes de habilitar gestión en Azure, crea una tabla persistente de alertas y auditoría.")
    if alert_id not in {a["id"] for a in get_alerts()}:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO alert_status(alert_id,status,comment,updated_at) VALUES(:id,:status,:comment,CURRENT_TIMESTAMP) ON CONFLICT(alert_id) DO UPDATE SET status=excluded.status,comment=excluded.comment,updated_at=CURRENT_TIMESTAMP"),
                     {"id": alert_id, "status": status, "comment": payload.get("comment")})
    return {"ok": True, "id": alert_id, "status": status}
