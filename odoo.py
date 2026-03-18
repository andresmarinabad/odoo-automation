import xmlrpc.client
import os
import random
import calendar
import argparse
from datetime import date, datetime, timedelta
import pytz
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

ZONA_HORARIA = pytz.timezone("Europe/Madrid")

def calcular_horarios(fecha_base):
    # Asegurar datetime (puede llegar un date desde rellenar_rango)
    if isinstance(fecha_base, date) and not isinstance(fecha_base, datetime):
        fecha_base = datetime.combine(fecha_base, datetime.min.time())
    # 1. Entrada Mañana (08:00:00 - 09:00:00)
    # Generamos de 0 a 3600 segundos aleatorios (1 hora)
    segundos_inicio = random.randint(0, 3600)
    inicio_m = fecha_base.replace(hour=8, minute=0, second=0) + timedelta(seconds=segundos_inicio)
    
    # 2. Duración primer bloque (Máximo 5.5h = 19800 seg, mínimo 4h = 14400 seg)
    duracion_1_segundos = random.randint(14400, 19800)
    salida_m = inicio_m + timedelta(seconds=duracion_1_segundos)
    
    # Validar que no pase de las 15:00:00
    limite_almuerzo = fecha_base.replace(hour=15, minute=0, second=0)
    if salida_m > limite_almuerzo:
        salida_m = limite_almuerzo
        duracion_1_segundos = int((salida_m - inicio_m).total_seconds())

    # 3. Descanso (Entre 15 y 20 minutos -> de 900 a 1200 segundos)
    descanso_segundos = random.randint(900, 1200)
    inicio_t = salida_m + timedelta(seconds=descanso_segundos)

    # 4. Segundo bloque para completar 8 horas exactas (28.800 segundos)
    segundos_restantes = 28800 - duracion_1_segundos
    salida_t = inicio_t + timedelta(seconds=segundos_restantes)

    # 5. Validación final de hora de salida (Máximo 17:30:00)
    limite_maximo = fecha_base.replace(hour=17, minute=30, second=0)
    if salida_t > limite_maximo:
        return calcular_horarios(fecha_base) # Reintentar si la combinación se pasa de hora

    return inicio_m, salida_m, inicio_t, salida_t

def a_utc_str(dt_naive):
    """Localiza la fecha/hora en España y la convierte al formato UTC para Odoo"""
    dt_loc = ZONA_HORARIA.localize(dt_naive)
    dt_utc = dt_loc.astimezone(pytz.utc)
    return dt_utc.strftime('%Y-%m-%d %H:%M:%S')


def get_dias_con_registros(models, db, uid, api_key, employee_id, fecha_inicio, fecha_fin):
    """Devuelve un set de fechas (date) que ya tienen al menos un registro de asistencia."""
    # Buscar attendances del empleado en el rango
    dt_inicio = ZONA_HORARIA.localize(
        datetime.combine(fecha_inicio, datetime.min.time())
    ).astimezone(pytz.utc)
    dt_fin = ZONA_HORARIA.localize(
        datetime.combine(fecha_fin, datetime.max.time().replace(microsecond=0))
    ).astimezone(pytz.utc)
    str_inicio = dt_inicio.strftime('%Y-%m-%d %H:%M:%S')
    str_fin = dt_fin.strftime('%Y-%m-%d %H:%M:%S')

    ids = models.execute_kw(
        db, uid, api_key, 'hr.attendance', 'search',
        [[
            ['employee_id', '=', employee_id],
            ['check_in', '>=', str_inicio],
            ['check_in', '<=', str_fin],
        ]],
        {'order': 'check_in'}
    )
    if not ids:
        return set()

    registros = models.execute_kw(
        db, uid, api_key, 'hr.attendance', 'read',
        [ids], {'fields': ['check_in']}
    )
    dias = set()
    for r in registros:
        # check_in viene en UTC; pasamos a fecha local para el día
        check_in_str = r['check_in']
        if isinstance(check_in_str, str):
            dt_utc = datetime.strptime(check_in_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
        else:
            dt_utc = check_in_str.replace(tzinfo=pytz.utc) if check_in_str.tzinfo is None else check_in_str
        dt_local = dt_utc.astimezone(ZONA_HORARIA)
        dias.add(dt_local.date())
    return dias


def rellenar_rango(fecha_inicio, fecha_fin, etiqueta="rango"):
    """Rellena días laborables en [fecha_inicio, fecha_fin]. No toca días que ya tengan registros."""
    url = os.getenv("ODOO_URL").strip("/")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    api_key = os.getenv("ODOO_TOKEN")

    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    try:
        uid = common.authenticate(db, username, api_key, {})
        if not uid:
            print("❌ Error: No se pudo autenticar. Revisa tus credenciales.")
            return

        emp_ids = models.execute_kw(db, uid, api_key, 'hr.employee', 'search', [[['user_id', '=', uid]]])
        if not emp_ids:
            print("❌ Error: Tu usuario no tiene un Empleado vinculado en Odoo.")
            return

        employee_id = emp_ids[0]
        print(f"✅ Conectado. Empleado (ID: {employee_id})")
        print(f"📅 Rellenando {etiqueta} ({fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')})...\n")

        dias_con_registros = get_dias_con_registros(
            models, db, uid, api_key, employee_id, fecha_inicio, fecha_fin
        )

        creados = 0
        actual = fecha_inicio
        while actual <= fecha_fin:
            if actual.weekday() >= 5:  # sábado, domingo
                actual += timedelta(days=1)
                continue
            if actual in dias_con_registros:
                print(f"⏭️  {actual.strftime('%d/%m/%Y')} ya tiene registros, se omite.")
                actual += timedelta(days=1)
                continue

            i_m, s_m, i_t, s_t = calcular_horarios(actual)
            turnos = [
                {'check_in': a_utc_str(i_m), 'check_out': a_utc_str(s_m)},
                {'check_in': a_utc_str(i_t), 'check_out': a_utc_str(s_t)}
            ]
            for turno in turnos:
                models.execute_kw(db, uid, api_key, 'hr.attendance', 'create', [{
                    'employee_id': employee_id,
                    'check_in': turno['check_in'],
                    'check_out': turno['check_out'],
                }])
            print(f"✔️ {actual.strftime('%d/%m/%Y')} registrado: {i_m.strftime('%H:%M:%S')}->{s_m.strftime('%H:%M:%S')} y {i_t.strftime('%H:%M:%S')}->{s_t.strftime('%H:%M:%S')}")
            creados += 1
            actual += timedelta(days=1)

        print(f"\n🚀 {etiqueta} listo. Días creados: {creados}.")

    except Exception as e:
        print(f"💥 Ocurrió un error: {e}")


def borrar_rango(fecha_inicio, fecha_fin, etiqueta="rango"):
    """Borra todos los registros de asistencia del empleado en [fecha_inicio, fecha_fin]."""
    url = os.getenv("ODOO_URL").strip("/")
    db = os.getenv("ODOO_DB")
    username = os.getenv("ODOO_USER")
    api_key = os.getenv("ODOO_TOKEN")

    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

    try:
        uid = common.authenticate(db, username, api_key, {})
        if not uid:
            print("❌ Error: No se pudo autenticar. Revisa tus credenciales.")
            return

        emp_ids = models.execute_kw(db, uid, api_key, 'hr.employee', 'search', [[['user_id', '=', uid]]])
        if not emp_ids:
            print("❌ Error: Tu usuario no tiene un Empleado vinculado en Odoo.")
            return

        employee_id = emp_ids[0]
        dt_inicio = ZONA_HORARIA.localize(
            datetime.combine(fecha_inicio, datetime.min.time())
        ).astimezone(pytz.utc)
        dt_fin = ZONA_HORARIA.localize(
            datetime.combine(fecha_fin, datetime.max.time().replace(microsecond=0))
        ).astimezone(pytz.utc)
        str_inicio = dt_inicio.strftime('%Y-%m-%d %H:%M:%S')
        str_fin = dt_fin.strftime('%Y-%m-%d %H:%M:%S')

        ids = models.execute_kw(
            db, uid, api_key, 'hr.attendance', 'search',
            [[
                ['employee_id', '=', employee_id],
                ['check_in', '>=', str_inicio],
                ['check_in', '<=', str_fin],
            ]]
        )
        if not ids:
            print(f"⏭️  No hay registros en {etiqueta}.")
            return

        models.execute_kw(db, uid, api_key, 'hr.attendance', 'unlink', [ids])
        print(f"🗑️  Borrados {len(ids)} registros en {etiqueta}.")

    except Exception as e:
        print(f"💥 Ocurrió un error: {e}")


def rango_mes_actual():
    hoy = datetime.now().date()
    _, ultimo = calendar.monthrange(hoy.year, hoy.month)
    return hoy.replace(day=1), hoy.replace(day=ultimo)


def rango_semana_actual():
    hoy = datetime.now().date()
    # Lunes = 0
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes, domingo


def main():
    parser = argparse.ArgumentParser(
        description="Rellenar o borrar registros de asistencia Odoo (mes/semana actual)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--month',
        action='store_true',
        help='Rellenar el mes actual (solo días sin registros)',
    )
    group.add_argument(
        '--week',
        action='store_true',
        help='Rellenar la semana actual (solo días sin registros)',
    )
    group.add_argument(
        '--delete',
        choices=['month', 'week'],
        metavar='PERIODO',
        help='Borrar registros del mes o de la semana actual',
    )

    args = parser.parse_args()

    if args.delete:
        if args.delete == 'month':
            inicio, fin = rango_mes_actual()
            borrar_rango(inicio, fin, "mes actual")
        else:
            inicio, fin = rango_semana_actual()
            borrar_rango(inicio, fin, "semana actual")
    elif args.month:
        inicio, fin = rango_mes_actual()
        rellenar_rango(inicio, fin, "mes actual")
    else:  # args.week
        inicio, fin = rango_semana_actual()
        rellenar_rango(inicio, fin, "semana actual")


if __name__ == "__main__":
    main()