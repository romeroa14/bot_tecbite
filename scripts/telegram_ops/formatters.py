from __future__ import annotations

from datetime import datetime
from typing import Any

from .notify import escape_html


def _veh(row: dict) -> str:
    parts = [row.get("make"), row.get("model"), row.get("year")]
    text = " ".join(str(p) for p in parts if p)
    return text or "—"


def _ago(dt: datetime | None) -> str:
    if not dt:
        return "—"
    mins = int((datetime.now(dt.tzinfo) - dt).total_seconds() // 60)
    if mins < 1:
        return "ahora"
    if mins < 60:
        return f"hace {mins}m"
    hrs = mins // 60
    if hrs < 24:
        return f"hace {hrs}h"
    return f"hace {hrs // 24}d"


def help_text() -> str:
    return (
        "🤖 <b>Tecbite — Ops Instagram</b>\n\n"
        "Comandos:\n"
        "/hoy — resumen del día\n"
        "/activos — hilos recientes (6h)\n"
        "/handoffs — escalamientos WhatsApp\n"
        "/cliente — detalle (ej: /cliente 222523… o Toyota Corolla)\n"
        "/stats — KPIs técnicos 24h\n"
        "/help — esta ayuda\n\n"
        "Las alertas automáticas llegan cuando hay lead listo o handoff."
    )


def format_today(row: dict) -> str:
    return (
        "📊 <b>Hoy — Instagram DM</b>\n\n"
        f"👥 Conversaciones: <b>{row.get('total', 0)}</b>\n"
        f"✅ Leads completos: <b>{row.get('ready', 0)}</b>\n"
        f"📞 Handoffs: <b>{row.get('handoffs', 0)}</b>\n"
        f"🚗 Barras: {row.get('barras', 0)} · 🧽 WT: {row.get('alfombras', 0)}"
    )


def format_active(rows: list[dict]) -> str:
    if not rows:
        return "💤 No hay hilos activos en las últimas 6 horas."
    lines = ["🔥 <b>Activos (6h)</b>\n"]
    for r in rows[:10]:
        cid = str(r.get("conversation_id", ""))[:14]
        lines.append(
            f"• <code>{escape_html(cid)}</code> · {escape_html(_veh(r))}\n"
            f"  {escape_html(r.get('category') or '—')} · {escape_html(r.get('stage'))} · {_ago(r.get('updated_at'))}"
        )
    lines.append("\n<i>Detalle: /cliente &lt;id&gt;</i>")
    return "\n".join(lines)


def format_handoffs(rows: list[dict]) -> str:
    if not rows:
        return "✅ Sin handoffs pendientes recientes."
    lines = ["📞 <b>Handoffs / WhatsApp</b>\n"]
    for r in rows:
        cid = str(r.get("conversation_id", ""))[:14]
        lines.append(
            f"• <code>{escape_html(cid)}</code> · {escape_html(_veh(r))}\n"
            f"  {escape_html(r.get('category') or '—')} · {_ago(r.get('updated_at'))}"
        )
    return "\n".join(lines)


def format_client(row: dict) -> str:
    if not row:
        return "No encontré ese cliente."
    lines = [
        "👤 <b>Lead Instagram</b>\n",
        f"ID: <code>{escape_html(row.get('conversation_id'))}</code>",
        f"Vehículo: <b>{escape_html(_veh(row))}</b>",
        f"Categoría: {escape_html(row.get('category') or '—')}",
        f"Etapa: {escape_html(row.get('stage'))} · Techo: {escape_html(row.get('roof_type') or '—')}",
        f"Slots OK: {'sí' if row.get('slots_complete') else 'no'}",
        f"Actualizado: {_ago(row.get('updated_at'))}\n",
        "<b>Últimos eventos:</b>",
    ]
    events = row.get("events") or []
    if isinstance(events, str):
        import json

        events = json.loads(events)
    for ev in (events or [])[:6]:
        text = str(ev.get("text", "")).replace("\n", " ")[:120]
        lines.append(
            f"• [{escape_html(ev.get('event_type'))}] {escape_html(text)}"
        )
    return "\n".join(lines)


def format_search_results(rows: list[dict]) -> str:
    if not rows:
        return "Sin coincidencias."
    lines = ["🔍 <b>Resultados</b>\n"]
    for r in rows:
        lines.append(
            f"• <code>{escape_html(r.get('conversation_id'))}</code> · "
            f"{escape_html(_veh(r))} · {escape_html(r.get('category') or '—')}"
        )
    lines.append("\nDetalle: /cliente &lt;id&gt;")
    return "\n".join(lines)


def format_stats(row: dict) -> str:
    return (
        "📈 <b>KPIs 24h</b>\n\n"
        f"Slots completos: <b>{row.get('slots_completion_percent', 0)}</b>%\n"
        f"Precisión fitment: <b>{row.get('compatibility_precision_percent', 0)}</b>%\n"
        f"Resp. sin fuente técnica: <b>{row.get('technical_without_source_percent', 0)}</b>%\n"
        f"Latencia técnica p95: <b>{row.get('technical_latency_p95_ms', 0)}</b> ms"
    )


def format_push(notify_type: str, data: dict[str, Any]) -> str:
    veh = escape_html(_veh(data))
    cat = escape_html(data.get("category") or "—")
    cid = escape_html(str(data.get("conversation_id", ""))[:18])
    if notify_type == "handoff":
        return (
            "📞 <b>Handoff — asesor humano</b>\n\n"
            f"Cliente: <code>{cid}</code>\n"
            f"Vehículo: <b>{veh}</b>\n"
            f"Producto: {cat}\n"
            f"Mensaje: {escape_html(str(data.get('inbound_text', ''))[:100])}"
        )
    if notify_type == "lead_ready":
        roof = data.get("roof_type")
        extra = f"\nTecho: {escape_html(roof)}" if roof else ""
        return (
            "✅ <b>Lead listo para cotizar</b>\n\n"
            f"Cliente: <code>{cid}</code>\n"
            f"Vehículo: <b>{veh}</b>\n"
            f"Producto: {cat}{extra}"
        )
    if notify_type == "new_vehicle":
        return (
            "🆕 <b>Nuevo vehículo en hilo</b>\n\n"
            f"Cliente: <code>{cid}</code>\n"
            f"Vehículo: <b>{veh}</b>\n"
            f"Producto: {cat}"
        )
    if notify_type == "category_switch":
        return (
            "🔀 <b>Cambio de producto</b>\n\n"
            f"Cliente: <code>{cid}</code>\n"
            f"Vehículo: <b>{veh}</b>\n"
            f"Antes: {escape_html(data.get('prev_category') or '—')}\n"
            f"Ahora: <b>{cat}</b>"
        )
    return f"ℹ️ Ops: <code>{cid}</code> · {veh} · {cat}"
