import xmlrpc.client
import os
import random
import calendar
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Cargar variables de entorno (ODOO_URL, ODOO_DB, ODOO_USER, ODOO_TOKEN)
load_dotenv()

# ==========================================
# CONFIGURACIÓN DEL MES A RELLENAR
# ==========================================
AÑO = 2026
MES = 3
# ==========================================

ZONA_HORARIA = pytz.timezone("Europe/Madrid")

def calcular_horarios(fecha_base):
    # 1. Entrada Mañana (08:00 - 09:00)
    inicio_m = fecha_base.replace(hour=8, minute=0, second=0) + timedelta(minutes=random.randint(0, 60))
    
    # 2. Duración primer bloque (Máximo 5.5h para no pasar de 6h seguidas)
    duracion_1 = random.randint(240, 330) 
    salida_m = inicio_m + timedelta(minutes=duracion_1)
    
    # Validar que no pase de las 15:00
    limite_almuerzo = fecha_base.replace(hour=15, minute=0, second=0)
    if salida_m > limite_almuerzo:
        salida_m = limite_almuerzo
        duracion_1 = int((salida_m - inicio_m).total_seconds() / 60)

    # 3. Descanso (15 - 20 minutos)
    descanso = random.randint(15, 20)
    inicio_t = salida_m + timedelta(minutes=descanso)

    # 4. Segundo bloque para completar 8 horas (480 min exactos)
    minutos_restantes = 480 - duracion_1
    salida_t = inicio_t + timedelta(minutes=minutos_restantes)

    # 5. Validación final de hora de salida (Máximo 17:30)
    limite_maximo = fecha_base.replace(hour=17, minute=30, second=0)
    if salida_t > limite_maximo:
        return calcular_horarios(fecha_base) # Reintentar si la combinación aleatoria se pasa

    return inicio_m, salida_m, inicio_t, salida_t

def a_utc_str(dt_naive):
    """Localiza la fecha/hora en España y la convierte al formato UTC para Odoo"""
    dt_loc = ZONA_HORARIA.localize(dt_naive)
    dt_utc = dt_loc.astimezone(pytz.utc)
    return dt_utc.strftime('%Y-%m-%d %H:%M:%S')

def registrar_mes_completo():
    # Parámetros de conexión desde .env
    url = os.getenv("ODOO_URL").strip("/")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    api_key = os.getenv("ODOO_TOKEN")

    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    try:
        # Autenticación
        uid = common.authenticate(db, username, api_key, {})
        if not uid:
            print("❌ Error: No se pudo autenticar. Revisa tus credenciales.")
            return
        
        print(f"✅ Conectado con UID: {uid}")

        # Búsqueda automática del ID del Empleado
        emp_ids = models.execute_kw(db, uid, api_key, 'hr.employee', 'search', [[['user_id', '=', uid]]])
        if not emp_ids:
            print("❌ Error: Tu usuario no tiene un Empleado vinculado en Odoo.")
            return
        
        employee_id = emp_ids[0]
        print(f"👤 Empleado detectado (ID: {employee_id})")
        print(f"📅 Generando registros para {MES}/{AÑO}...\n")

        # Obtener los días del mes
        _, num_dias = calendar.monthrange(AÑO, MES)

        # Bucle para recorrer cada día del mes
        for dia in range(1, num_dias + 1):
            fecha_actual = datetime(AÑO, MES, dia)
            
            # Saltar sábados (5) y domingos (6)
            if fecha_actual.weekday() >= 5:
                continue
                
            # Calcular horarios para este día
            i_m, s_m, i_t, s_t = calcular_horarios(fecha_actual)

            # Preparar los turnos convirtiendo a UTC
            turnos = [
                {'check_in': a_utc_str(i_m), 'check_out': a_utc_str(s_m)},
                {'check_in': a_utc_str(i_t), 'check_out': a_utc_str(s_t)}
            ]

            # Enviar a Odoo
            for turno in turnos:
                res_id = models.execute_kw(db, uid, api_key, 'hr.attendance', 'create', [{
                    'employee_id': employee_id,
                    'check_in': turno['check_in'],
                    'check_out': turno['check_out'],
                }])
            
            print(f"✔️ {fecha_actual.strftime('%d/%m/%Y')} registrado: {i_m.strftime('%H:%M')}->{s_m.strftime('%H:%M')} y {i_t.strftime('%H:%M')}->{s_t.strftime('%H:%M')}")

        print("\n🚀 ¡Mes completado con éxito!")

    except Exception as e:
        print(f"💥 Ocurrió un error: {e}")

if __name__ == "__main__":
    registrar_mes_completo()