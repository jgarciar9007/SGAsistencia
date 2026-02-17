# dispositivos/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
import socket
from zoneinfo import ZoneInfo
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import StreamingHttpResponse
from datetime import datetime
from django.utils.dateparse import  parse_date
from .models import Dispositivo, UsuarioDispositivo, AsistenciaCruda
from .forms import DispositivoForm
from datetime import timezone as dt_timezone
from django.utils.timezone import localtime



def _solo_admin(user):
    return user.is_authenticated and user.is_superuser


def _get_ZK():
    try:
        from zk import ZK  # pyzk / pyzk2
        return ZK
    except Exception:
        pass
    try:
        from pyzk import ZK
        return ZK
    except Exception:
        pass
    try:
        from pyzk.zk import ZK
        return ZK
    except Exception as e:
        raise RuntimeError("SDK ZKTeco no disponible. Instala: pip install pyzk (o pyzk2).") from e


def _conn_with_fallbacks(dispositivo):
    """
    Autentica probando varias contraseñas:
    1) La almacenada en el registro
    2) '1234' (frecuente)
    3) '0'
    4) '' (vacía)
    Evita password=None para esquivar int(None) en algunos SDK.
    Devuelve (conn, pwd_usada).
    """
    ZK = _get_ZK()

    raw = (dispositivo.password.strip() if dispositivo.password else None)
    candidates = []
    if raw not in (None, ''):
        candidates.append(raw)
    candidates.extend(['1234', '0', ''])  # comunes
    tried = set()
    last_exc = None

    for pwd in candidates:
        if pwd in tried:
            continue
        tried.add(pwd)
        try:
            zk = ZK(
                dispositivo.ip,
                port=dispositivo.puerto,
                timeout=dispositivo.timeout,
                password=pwd,  # nunca None
                force_udp=(dispositivo.protocolo == 'udp'),
                ommit_ping=dispositivo.omitir_ping,
                verbose=False,
            )
            conn = zk.connect()
            return conn, pwd
        except Exception as e:
            last_exc = e
            continue

    raise last_exc if last_exc else RuntimeError("No fue posible autenticar.")


@login_required
@user_passes_test(_solo_admin)
def config_index(request):
    dispositivos = Dispositivo.objects.all()
    return render(request, 'dispositivos/dispositivo_list.html', {'dispositivos': dispositivos})


@login_required
@user_passes_test(_solo_admin)
def dispositivo_crear(request):
    if request.method == 'POST':
        form = DispositivoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Dispositivo creado.")
            return redirect('config:index')
    else:
        form = DispositivoForm()
    return render(request, 'dispositivos/dispositivo_form.html', {'form': form, 'modo': 'crear'})


@login_required
@user_passes_test(_solo_admin)
def dispositivo_editar(request, pk):
    obj = get_object_or_404(Dispositivo, pk=pk)
    if request.method == 'POST':
        form = DispositivoForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Dispositivo actualizado.")
            return redirect('config:index')
    else:
        form = DispositivoForm(instance=obj)
    return render(request, 'dispositivos/dispositivo_form.html', {'form': form, 'modo': 'editar', 'obj': obj})


@login_required
@user_passes_test(_solo_admin)
def dispositivo_eliminar(request, pk):
    obj = get_object_or_404(Dispositivo, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, "Dispositivo eliminado.")
        return redirect('config:index')
    return render(request, 'dispositivos/dispositivo_confirm_delete.html', {'obj': obj})


@login_required
@user_passes_test(_solo_admin)
def dispositivo_probar_conexion(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")
    d = get_object_or_404(Dispositivo, pk=pk)
    try:
        if d.protocolo == 'tcp':
            with socket.create_connection((d.ip, d.puerto), timeout=d.timeout):
                pass
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(d.timeout)
            sock.sendto(b'', (d.ip, d.puerto))
            try:
                sock.recvfrom(1)
            except socket.timeout:
                pass
            finally:
                sock.close()

        conn, used = _conn_with_fallbacks(d)
        fw = getattr(conn, 'firmware_version', None)
        conn.disconnect()
        messages.success(request, f"Conectado. Password usada: '{used}'. Firmware: {fw or 'N/D'}.")
    except Exception as ex:
        messages.error(request, f"No autenticó: {ex.__class__.__name__}: {ex}")
    return HttpResponseRedirect(reverse('config:index'))


@login_required
@user_passes_test(_solo_admin)
def descargar_usuarios(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")

    dispositivo = get_object_or_404(Dispositivo, pk=pk)

    def _get(obj, *names, default=None):
        # Lee primero de vars(obj) y luego via getattr
        d = {}
        try:
            d = vars(obj)
        except Exception:
            d = {}
        for n in names:
            if n in d:
                return d[n]
            try:
                return getattr(obj, n)
            except Exception:
                pass
        return default

    def _to_int_or_none(v):
        try:
            if v is None:
                return None
            if isinstance(v, int):
                return v
            s = str(v).strip()
            return int(s) if s != '' else None
        except Exception:
            return None

    def _to_str(v, maxlen):
        s = '' if v is None else str(v)
        s = s.strip()
        return s[:maxlen]

    try:
        conn, used = _conn_with_fallbacks(dispositivo)
        users = conn.get_users()

        print(f"[DEBUG] Usuarios recibidos del equipo: {len(users)}")
        if users:
            try:
                sample = users[0]
                print("[DEBUG] Ejemplo de usuario:", vars(sample))
            except Exception:
                pass

        creados = actualizados = omitidos = err = 0

        for u in users:
            try:
                uid_val = _to_int_or_none(_get(u, "uid", "UID", "id"))
                user_id_val = _to_str(_get(u, "user_id", "userid", "UserID"), 32)
                nombre_val = _to_str(_get(u, "name", "Name", "username", "user_name"), 64)

                privilegio_raw = _get(u, "privilege", "Privilege", default=None)
                privilegio_val = _to_int_or_none(privilegio_raw)

                grupo_raw = _get(u, "group_id", "group", "Group", default=None)
                grupo_val = _to_int_or_none(grupo_raw)

                # Clave de búsqueda:
                # 1) Si hay user_id no vacío, usar (dispositivo, user_id)
                # 2) Si no, y hay uid, usar (dispositivo, uid)
                # 3) Si no hay ninguno, omitir
                if user_id_val:
                    lookup = dict(dispositivo=dispositivo, user_id=user_id_val)
                elif uid_val is not None:
                    lookup = dict(dispositivo=dispositivo, uid=uid_val)
                else:
                    omitidos += 1
                    continue

                # Defaults a actualizar
                defaults = dict(
                    uid=uid_val,
                    user_id=user_id_val,
                    nombre=nombre_val,
                    privilegio=privilegio_val,
                    grupo_id=grupo_val,
                    activo=True,
                )

                obj, created = UsuarioDispositivo.objects.update_or_create(
                    **lookup, defaults=defaults
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

            except Exception as e:
                err += 1
                print("[DEBUG] Error guardando usuario:", type(e).__name__, e, "datos=", {
                    "uid": _get(u, "uid", default=None),
                    "user_id": _get(u, "user_id", default=None),
                    "name": _get(u, "name", default=None),
                    "privilege": _get(u, "privilege", default=None),
                    "group_id": _get(u, "group_id", default=None),
                })
                continue

        conn.disconnect()
        messages.success(
            request,
            f"Usuarios: {creados} creados, {actualizados} actualizados, {omitidos} omitidos, {err} con error. Password usada: '{used}'."
        )
    except Exception as e:
        messages.error(request, f"Error descargando usuarios: {e.__class__.__name__}: {e}")

    return redirect('config:index')



@login_required
@user_passes_test(_solo_admin)
def descargar_asistencia(request, pk):
    if request.method != 'POST':
        return HttpResponseForbidden("Método no permitido")

    dispositivo = get_object_or_404(Dispositivo, pk=pk)
    tz_local = ZoneInfo(dispositivo.tz or 'Africa/Malabo')

    try:
        conn, used = _conn_with_fallbacks(dispositivo)
        logs = conn.get_attendance()

        print(f"[DEBUG] Total logs recibidos: {len(logs)}")
        if logs:
            print("[DEBUG] Estructura del primer log:")
            try:
                print(vars(logs[0]))
            except Exception as e:
                print("vars(logs[0]) dio error:", type(e).__name__, e)
            print("dir(logs[0]):", dir(logs[0]))
            print("repr(logs[0]):", repr(logs[0]))

        mapa_usuarios = {
            u.user_id: u for u in UsuarioDispositivo.objects.filter(dispositivo=dispositivo)
        }

        objs = []
        for r in logs:
            try:
                data = vars(r)
                ts = data.get("timestamp")
                if not isinstance(ts, datetime):
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=tz_local)
                ts_utc = ts.astimezone(dt_timezone.utc)

                uid_val = data.get("uid")
                if isinstance(uid_val, str) and uid_val.isdigit():
                    uid_val = int(uid_val)

                user_id_val = str(data.get("user_id") or "").strip()
                if not user_id_val:
                    user_id_val = str(uid_val or "")

                status_val = int(data.get("status") or 0)
                punch_val = data.get("punch")
                try:
                    punch_val = int(punch_val)
                except (TypeError, ValueError):
                    punch_val = None

                objs.append(
                    AsistenciaCruda(
                        dispositivo=dispositivo,
                        usuario=mapa_usuarios.get(user_id_val),
                        user_id=user_id_val,
                        uid=uid_val,
                        ts=ts_utc,
                        status=status_val,
                        punch=punch_val,
                        raw_status=str(data.get("status")),
                    )
                )
            except Exception as e:
                print("[DEBUG] error procesando log:", type(e).__name__, e)
                continue

        print(f"[DEBUG] Registros listos para insertar: {len(objs)}")

        if objs:
            AsistenciaCruda.objects.bulk_create(objs, ignore_conflicts=True)
            total_db = AsistenciaCruda.objects.filter(dispositivo=dispositivo).count()
            print(f"[DEBUG] Insertados en DB: {len(objs)}")
            print(f"[DEBUG] Total acumulado en DB para {dispositivo.nombre}: {total_db}")
        else:
            print("[DEBUG] No se prepararon registros válidos.")

        conn.disconnect()
        messages.success(
            request,
            f"Procesados {len(logs)} registros. Password usada: '{used}'.",
        )
    except Exception as e:
        messages.error(
            request,
            f"Error al descargar registros: {e.__class__.__name__}: {e}",
        )
    return redirect('config:index')



@login_required
@user_passes_test(_solo_admin)
def asistencia_list(request):
    """
    Listado con filtros:
    - q: busca en user_id y dispositivo.nombre
    - desde, hasta: fechas (YYYY-MM-DD)
    - dispositivo: id
    Pagina en 50 items.
    """
    qs = AsistenciaCruda.objects.select_related("dispositivo").order_by("-ts")

    # [MODIFICADO] Solo mostrar registros de usuarios vinculados a un empleado
    qs = qs.filter(usuario__empleado__isnull=False)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(user_id__icontains=q) | Q(dispositivo__nombre__icontains=q))

    dispositivo_id = request.GET.get("dispositivo")
    if dispositivo_id:
        qs = qs.filter(dispositivo_id=dispositivo_id)

    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")

    def _to_dt(d, end=False):
        if not d:
            return None
        try:
            dt = parse_date(d)
            if not dt:
                return None
            if end:
                return datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=timezone.utc)
            return datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=timezone.utc)
        except Exception:
            return None

    dt_desde = _to_dt(desde, end=False)
    dt_hasta = _to_dt(hasta, end=True)

    if dt_desde:
        qs = qs.filter(ts__gte=dt_desde)
    if dt_hasta:
        qs = qs.filter(ts__lte=dt_hasta)

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    dispositivos = Dispositivo.objects.order_by("nombre").values("id", "nombre")

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "desde": desde or "",
        "hasta": hasta or "",
        "dispositivos": dispositivos,
        "dispositivo_sel": int(dispositivo_id) if dispositivo_id else None,
        "total": qs.count(),
    }
    return render(request, "dispositivos/asistencia_list.html", ctx)


@login_required
@user_passes_test(_solo_admin)
def asistencia_export_csv(request):
    """
    Exporta el mismo filtro actual a CSV.
    Columnas: ts,user_id,dispositivo,status,punch
    """
    # Reusar la lógica de filtros de asistencia_list
    qs = AsistenciaCruda.objects.select_related("dispositivo").order_by("ts")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(user_id__icontains=q) | Q(dispositivo__nombre__icontains=q))
    dispositivo_id = request.GET.get("dispositivo")
    if dispositivo_id:
        qs = qs.filter(dispositivo_id=dispositivo_id)
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")

    def _to_dt(d, end=False):
        if not d:
            return None
        dt = parse_date(d)
        if not dt:
            return None
        if end:
            return datetime(dt.year, dt.month, dt.day, 23, 59, 59, tzinfo=timezone.utc)
        return datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=timezone.utc)

    dt_desde = _to_dt(desde, end=False)
    dt_hasta = _to_dt(hasta, end=True)
    if dt_desde:
        qs = qs.filter(ts__gte=dt_desde)
    if dt_hasta:
        qs = qs.filter(ts__lte=dt_hasta)

    def row_iter():
        yield "ts,user_id,dispositivo,status,punch\r\n"
        for r in qs.iterator(chunk_size=1000):
            yield f"{r.ts.isoformat()},{r.user_id},{r.dispositivo.nombre},{r.status},{'' if r.punch is None else r.punch}\r\n"

    resp = StreamingHttpResponse(row_iter(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="asistencias.csv"'
    return resp

    
@login_required
@user_passes_test(_solo_admin)
def usuario_list(request):
    """
    Lista usuarios del dispositivo con filtros:
    - q: busca en user_id y nombre y dispositivo.nombre
    - dispositivo: id
    - activo: '1' o '0'
    """
    qs = UsuarioDispositivo.objects.select_related("dispositivo").all().order_by("dispositivo__nombre", "user_id")

    q = (request.GET.get("q") or "").strip()
    dispositivo_id = (request.GET.get("dispositivo") or "").strip()
    activo = request.GET.get("activo")

    if q:
        qs = qs.filter(
            Q(user_id__icontains=q) |
            Q(nombre__icontains=q) |
            Q(dispositivo__nombre__icontains=q)
        )
    if dispositivo_id:
        qs = qs.filter(dispositivo_id=dispositivo_id)
    if activo in ("0", "1"):
        qs = qs.filter(activo=(activo == "1"))

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "page_obj": page_obj,
        "q": q,
        "dispositivos": Dispositivo.objects.order_by("nombre").values("id", "nombre"),
        "dispositivo_sel": int(dispositivo_id) if dispositivo_id else None,
        "activo": activo if activo in ("0","1") else "",
        "total": qs.count(),
    }
    return render(request, "dispositivos/usuario_list.html", ctx)


@login_required
@user_passes_test(_solo_admin)
def usuario_export_csv(request):
    qs = UsuarioDispositivo.objects.select_related("dispositivo").all().order_by("dispositivo__nombre", "user_id")

    q = (request.GET.get("q") or "").strip()
    dispositivo_id = (request.GET.get("dispositivo") or "").strip()
    activo = request.GET.get("activo")

    if q:
        qs = qs.filter(
            Q(user_id__icontains=q) |
            Q(nombre__icontains=q) |
            Q(dispositivo__nombre__icontains=q)
        )
    if dispositivo_id:
        qs = qs.filter(dispositivo_id=dispositivo_id)
    if activo in ("0","1"):
        qs = qs.filter(activo=(activo == "1"))

    def row_iter():
        yield "dispositivo,user_id,nombre,uid,privilegio,grupo_id,activo\r\n"
        for u in qs.iterator(chunk_size=1000):
            yield f"{u.dispositivo.nombre},{u.user_id},{u.nombre},{u.uid or ''},{'' if u.privilegio is None else u.privilegio},{'' if u.grupo_id is None else u.grupo_id},{1 if u.activo else 0}\r\n"

    resp = StreamingHttpResponse(row_iter(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="usuarios_dispositivo.csv"'
    return resp




@login_required
def reporte_asistencia(request):
    """
    Reporte diario: primera entrada y última salida por usuario.
    Muestra el nombre real si existe; si no, cae al user_id.
    """
    # [MODIFICADO] Solo mostrar registros de usuarios vinculados a un empleado
    qs = AsistenciaCruda.objects.select_related("dispositivo", "usuario", "usuario__empleado").filter(usuario__empleado__isnull=False).order_by("ts")

    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    user_q = (request.GET.get("user_id") or "").strip()

    if desde:
        try:
            d0 = datetime.strptime(desde, "%Y-%m-%d").replace(tzinfo=dt_timezone.utc)
            qs = qs.filter(ts__gte=d0)
        except Exception:
            pass
    if hasta:
        try:
            d1 = datetime.strptime(hasta, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=dt_timezone.utc)
            qs = qs.filter(ts__lte=d1)
        except Exception:
            pass
    from django.db.models import Exists, OuterRef, Q

    qtext = (request.GET.get("user_id") or "").strip()  # usa el campo del formulario
    if qtext:
        same_user_name = UsuarioDispositivo.objects.filter(
            dispositivo_id=OuterRef('dispositivo_id'),
            user_id=OuterRef('user_id'),
            nombre__icontains=qtext,
        )
        qs = qs.filter(
            Q(user_id__icontains=qtext) |
            Q(usuario__nombre__icontains=qtext) |
            Exists(same_user_name)
    )


    # Mapas para resolver nombre aunque usuario FK sea nulo
    # Se cargan solo los usuarios de los dispositivos presentes en el queryset.
    disp_ids = list(qs.values_list("dispositivo_id", flat=True).distinct())
    users = UsuarioDispositivo.objects.filter(dispositivo_id__in=disp_ids).only("dispositivo_id", "user_id", "uid", "nombre")
    name_by_user = { (u.dispositivo_id, (u.user_id or "").strip()): (u.nombre or "") for u in users if (u.user_id or "").strip() }
    name_by_uid  = { (u.dispositivo_id, u.uid): (u.nombre or "") for u in users if u.uid is not None }

    # Agrupar por usuario(fecha local)
    resumen = {}
    for r in qs:
        # [MODIFICADO] Saltar si no tiene empleado asociado (por seguridad extra, aunque ya venga filtrado)
        if not r.usuario or not r.usuario.empleado:
            continue

        fecha_local = localtime(r.ts).date()
        clave = (r.dispositivo_id, r.user_id, fecha_local)
        
        # [MODIFICADO] Usar solo nombre de empleado
        nombre = f"{r.usuario.empleado.nombre} {r.usuario.empleado.apellido}".strip()

        item = resumen.setdefault(clave, {
            "fecha": fecha_local,
            "nombre": nombre,
            "entrada": None,
            "salida": None,
            "dispositivo": r.dispositivo.nombre,
        })
        hl = localtime(r.ts)
        if not item["entrada"] or hl < item["entrada"]:
            item["entrada"] = hl
        if not item["salida"] or hl > item["salida"]:
            item["salida"] = hl

    registros = []
    for item in resumen.values():
        ent, sal = item["entrada"], item["salida"]
        horas = ""
        if ent and sal:
            horas = f"{(sal - ent).total_seconds()/3600:.2f}"
        registros.append({
            "fecha": item["fecha"],
            "nombre": item["nombre"],
            "entrada": ent.strftime("%H:%M:%S") if ent else "",
            "salida": sal.strftime("%H:%M:%S") if sal else "",
            "total_horas": horas,
            "dispositivo": item["dispositivo"],
        })

    registros.sort(key=lambda x: (x["fecha"], x["nombre"]))
    page_obj = Paginator(registros, 50).get_page(request.GET.get("page"))

    return render(request, "reportes/reporte_asistencia.html", {
        "page_obj": page_obj,
        "desde": desde or "",
        "hasta": hasta or "",
        "user_id": user_q,
    })

