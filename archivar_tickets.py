"""
Script de archivado -- Torre de Control FTTH
================================================
Borra de PostgreSQL los tickets CERRADOS mas antiguos que ARCHIVE_MONTHS,
pero SOLO despues de confirmar que cada uno ya quedo guardado en el Google
Sheet (usa la misma funcion sync_ticket_to_sheets que ya usa la app, para
garantizar el mismo formato de fila).

Seguridad:
- Corre en modo "simulacro" por defecto: te dice qué borraría, sin borrar
  nada. Para borrar de verdad hay que agregar --confirmar.
- Si la variable GOOGLE_SHEETS_WEBHOOK_URL no esta configurada, el script
  se detiene sin borrar nada -- no hay forma de "confirmar en el sheet"
  si esa URL no existe, y no queremos borrar sin esa garantia.
- Si el POST al sheet falla para un ticket puntual, ESE ticket se omite
  (no se borra) y sigue con los demas.

Como ejecutarlo en Render:
  Dashboard -> tickets -> One-Off Jobs -> New Job
  Comando (simulacro, no borra nada):
      python archivar_tickets.py
  Comando (borra de verdad los que ya esten confirmados en el sheet):
      python archivar_tickets.py --confirmar

Variables opcionales:
  ARCHIVE_MONTHS=6   -> archiva lo cerrado hace mas de 6 meses (default: 12)
"""
import os
import sys
from datetime import datetime, timedelta

from app import app, db, Ticket, sync_ticket_to_sheets

ARCHIVE_MONTHS = int(os.environ.get('ARCHIVE_MONTHS', '12'))
CONFIRMAR = '--confirmar' in sys.argv


def main():
    if not os.environ.get('GOOGLE_SHEETS_WEBHOOK_URL', '').strip():
        print("GOOGLE_SHEETS_WEBHOOK_URL no esta configurada.")
        print("No se puede garantizar que el ticket quede en el sheet antes de borrarlo.")
        print("Configura esa variable primero. No se borro nada.")
        return

    limite = datetime.utcnow() - timedelta(days=30 * ARCHIVE_MONTHS)

    with app.app_context():
        candidatos = Ticket.query.filter(
            Ticket.estado == 'CERRADO',
            Ticket.fecha_cierre.isnot(None),
            Ticket.fecha_cierre < limite
        ).all()

        if not candidatos:
            print(f"No hay tickets CERRADOS de hace mas de {ARCHIVE_MONTHS} meses. Nada que archivar.")
            return

        modo = "BORRANDO" if CONFIRMAR else "SIMULACRO (nada se borra todavia)"
        print(f"[{modo}] {len(candidatos)} tickets candidatos, cerrados antes de {limite.date()}.\n")

        archivados, fallidos = 0, 0
        for t in candidatos:
            ok, msg = sync_ticket_to_sheets(t.to_dict(), action='archivo_final')
            if not ok:
                print(f"  x Ticket #{t.id} ({t.site}): no se pudo confirmar en el sheet -- {msg}. Se omite.")
                fallidos += 1
                continue

            if CONFIRMAR:
                db.session.delete(t)
                print(f"  ok Ticket #{t.id} ({t.site}, cerrado {t.fecha_cierre.date()}): confirmado en sheet, borrado de la base.")
            else:
                print(f"  ok Ticket #{t.id} ({t.site}, cerrado {t.fecha_cierre.date()}): confirmado en sheet, SE BORRARIA con --confirmar.")
            archivados += 1

        if CONFIRMAR:
            db.session.commit()

        print(f"\nResumen: {archivados} {'archivados y borrados' if CONFIRMAR else 'listos para archivar'}, {fallidos} omitidos por no poder confirmar el sheet.")
        if not CONFIRMAR:
            print("Vuelve a correr con --confirmar para borrar de verdad estos tickets de la base.")


if __name__ == '__main__':
    main()
