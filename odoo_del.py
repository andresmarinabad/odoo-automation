import xmlrpc.client
import os
import calendar
from datetime import datetime, time
import pytz
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ==========================================
# CONFIGURACIÓN DEL MES A BORRAR
# ==========================================
AÑO = 2026
MES = 3
# ==========================================

ZONA_HORARIA = pytz.timezone("Europe/Madrid")

def a_utc_str(dt_naive):
    """Localiza la fecha/hora en España y la convierte al formato UTC para Odoo"""
    dt_loc = ZONA_HORARIA.localize(dt_naive)
    dt_utc = dt_loc.astimezone(pytz.utc)
    return dt_utc.strftime('%Y-%m-%d %H:%M:%S')

def borrar_asistencias_mes():
    url = os.getenv("ODOO_URL").strip("/")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    api_key = os.getenv("ODOO_TOKEN")

    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    try:
        # 1. Autenticación
        uid = common.authenticate(db, username, api_key, {})
        if not uid:
            print("❌ Error: No se pudo autenticar.")
            return
        
        # 2. Búsqueda del ID del Empleado
        emp_ids = models.execute_kw(db, uid, api_key, 'hr.employee', 'search', [[['user_id', '=', uid]]])
        if not emp_ids:
            print("❌ Error: Tu usuario no tiene un Empleado vinculado.")
            return
        
        employee_id = emp_ids[0]
        print(f"✅ Conectado. Empleado detectado (ID: {employee_id})")

        # 3. Calcular el rango de fechas exacto del mes (Inicio y Fin)
        _, ultimo_dia = calendar.monthrange(AÑO, MES)
        
        # Fecha de inicio: Día 1 a las 00:00:00
        inicio_mes_local = datetime(AÑO, MES, 1, 0, 0, 0)
        # Fecha de fin: Último día a las 23:59:59
        fin_mes_local = datetime(AÑO, MES, ultimo_dia, 23, 59, 59)

        # Convertir a formato UTC de Odoo
        inicio_mes_utc = a_utc_str(inicio_mes_local)
        fin_mes_utc = a_utc_str(fin_mes_local)

        print(f"🔍 Buscando asistencias entre {inicio_mes_utc} y {fin_mes_utc} (UTC)...")

        # 4. Construir el dominio de búsqueda en Odoo
        # Buscamos registros de tu empleado donde el check_in esté dentro de ese mes
        dominio = [
            ('employee_id', '=', employee_id),
            ('check_in', '>=', inicio_mes_utc),
            ('check_in', '<=', fin_mes_utc)
        ]

        # Obtener los IDs de los registros que coinciden
        asistencias_ids = models.execute_kw(db, uid, api_key, 'hr.attendance', 'search', [dominio])

        if not asistencias_ids:
            print("🤷‍♂️ No se encontraron asistencias para borrar en ese mes.")
            return

        print(f"⚠️ Se han encontrado {len(asistencias_ids)} registros de asistencia.")
        
        # Opcional: Pedir confirmación antes de borrar (descomenta si quieres doble seguridad)
        # confirmacion = input(f"¿Estás seguro de que quieres borrar {len(asistencias_ids)} registros? (s/N): ")
        # if confirmacion.lower() != 's':
        #     print("Cancelado.")
        #     return

        # 5. Ejecutar el borrado (unlink)
        models.execute_kw(db, uid, api_key, 'hr.attendance', 'unlink', [asistencias_ids])
        
        print(f"🗑️ ¡Éxito! Se han borrado {len(asistencias_ids)} registros de {MES}/{AÑO}.")

    except Exception as e:
        print(f"💥 Ocurrió un error: {e}")

if __name__ == "__main__":
    borrar_asistencias_mes()