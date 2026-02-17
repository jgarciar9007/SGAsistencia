from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.db.models import Q, Exists, OuterRef
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from dispositivos.models import UsuarioDispositivo, Dispositivo
from dispositivos.views import _conn_with_fallbacks
from .models import Empleado, Candidato, Documento, BajaAutorizada
from .forms import EmpleadoForm, VincularUsuarioForm, LinkUsuarioDispositivoForm, CandidatoForm, DocumentoForm, BajaAutorizadaForm


def _only_staff(u):
    return u.is_staff or u.is_superuser


# ======================
#  SDK SET USER (ODOO)
# ======================
def _sdk_set_user(conn, *, uid, user_id, name,
                  privilege=0, password="", group_id="0", card=0):
    """
    Firma igual al módulo de Odoo:
      zk.set_user(uid, name, privilege, password, group_id, user_id, card)

    Tipos:
      uid:int, privilege:int, card:int
      name:str, password:str, group_id:str, user_id:str
    """
    uid_int = int(str(uid).strip() or "0")
    priv_int = int(privilege or 0)
    card_int = int(card or 0)

    name_str = (name or "").strip()[:24]
    pwd_str = str(password or "")
    group_str = str(group_id or "0")
    user_str = (str(user_id or "").strip() or str(uid_int))[:32]

    return conn.set_user(
        uid_int,
        name_str,
        priv_int,
        pwd_str,
        group_str,
        user_str,
        card_int,
    )


# ======================
#  GENERADOR USER_ID
# ======================
def _siguiente_user_id(dispositivo: Dispositivo = None) -> str:
    """
    Generador infalible GLOBAL:
    - Empieza siempre en 200
    - Avanza en saltos de 10 (200, 210, 220...)
    - Comprueba que no exista en NINGÚN dispositivo ni en la tabla de Empleados.
    - El argumento 'dispositivo' se mantiene por compatibilidad pero no se limita a él.
    """
    base = 200
    step = 10
    
    # Obtener todos los IDs en uso (optimización)
    # 1. IDs en UsuarioDispositivo (todos los equipos)
    used_in_ud = set(UsuarioDispositivo.objects.values_list('user_id', flat=True))
    
    # 2. IDs en Empleados (histórico o asignados pero no sincronizados)
    used_in_emp = set(Empleado.objects.exclude(user_id="").values_list('user_id', flat=True))
    
    all_used = used_in_ud.union(used_in_emp)
    
    candidato = base
    while str(candidato) in all_used:
        candidato += step
        
    return str(candidato)



# ======================
#  LISTA DE EMPLEADOS
# ======================
@login_required
@user_passes_test(_only_staff)
def empleado_list(request):
    q = (request.GET.get("q") or "").strip()

    vinculo_qs = UsuarioDispositivo.objects.filter(empleado_id=OuterRef("pk"))
    qs = (Empleado.objects
          .all()
          .annotate(esta_vinculado=Exists(vinculo_qs)))
    # 1. Filtro por departamento
    depto = (request.GET.get("departamento") or "").strip()
    if depto:
        qs = qs.filter(departamento=depto)

    # 2. Orden alfabético por nombre
    qs = qs.order_by("nombre", "apellido")

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(numero__icontains=q) |
            Q(doc_id__icontains=q)
        )
    
    # Obtener lista de departamentos para el select
    departamentos = sorted([d for d in Empleado.objects.values_list("departamento", flat=True).distinct() if d])

    dispositivos = Dispositivo.objects.filter(activo=True).order_by("nombre").values("id", "nombre")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "empleados/empleado_list.html",
        {
            "page_obj": page_obj, 
            "q": q, 
            "dispositivos": dispositivos,
            "departamentos": departamentos,
            "depto_sel": depto,
        }
    )


@login_required
@user_passes_test(_only_staff)
def empleado_detalle(request, pk):
    obj = get_object_or_404(Empleado, pk=pk)
    documentos = obj.documentos.order_by("-subido_en")
    bajas = obj.bajas_autorizadas.order_by("-fecha_inicio")

    # Simple form for upload in modal or inline
    doc_form = DocumentoForm()

    return render(request, "empleados/empleado_detail.html", {
        "obj": obj,
        "documentos": documentos,
        "bajas": bajas,
        "doc_form": doc_form
    })


# ======================
#  CREAR EMPLEADO
# ======================
@login_required
@user_passes_test(_only_staff)
@transaction.atomic
def empleado_crear(request):
    form = EmpleadoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        emp: Empleado = form.save(commit=False)

        crear_en_equipo = form.cleaned_data.get("crear_en_dispositivo")
        disp = emp.dispositivo

        # Solo generamos user_id (UID lo dejamos en 0 para el equipo)
        if disp and not emp.user_id:
            emp.user_id = _siguiente_user_id(disp)

        emp.save()

        if disp:
            ud, _ = UsuarioDispositivo.objects.update_or_create(
                dispositivo=disp,
                user_id=emp.user_id or "",
                defaults={
                    "uid": emp.uid,  # puede ser None / 0; se actualizará al sincronizar
                    "nombre": emp.nombre_completo[:64],
                    "activo": emp.activo,
                    "empleado": emp,
                },
            )

            if crear_en_equipo:
                try:
                    conn, _ = _conn_with_fallbacks(disp)

                    try:
                        conn.disable_device()
                    except Exception:
                        pass

                    # uid=0 como acordado
                    _sdk_set_user(
                        conn,
                        uid=0,
                        user_id=emp.user_id or ud.user_id or "1000",
                        name=emp.nombre_completo[:24],
                        privilege=0,
                        password="",
                        group_id="0",
                        card=0,
                    )

                    try:
                        conn.refresh_data()
                    except Exception:
                        pass

                    try:
                        conn.enable_device()
                    except Exception:
                        pass

                    conn.disconnect()

                    messages.success(request, f"Empleado creado y sincronizado en {disp.nombre}.")
                except Exception as e:
                    messages.warning(request, f"Empleado creado, fallo en equipo: {type(e).__name__}: {e}")
            else:
                messages.success(request, "Empleado creado (vinculado).")
        else:
            messages.success(request, "Empleado creado.")

        return redirect("empleados:list")

    return render(request, "empleados/empleado_form.html", {"form": form, "modo": "crear"})


# ======================
#  EDITAR EMPLEADO
# ======================
@login_required
@user_passes_test(_only_staff)
@transaction.atomic
def empleado_editar(request, pk):
    emp = get_object_or_404(Empleado, pk=pk)
    form = EmpleadoForm(request.POST or None, request.FILES or None, instance=emp)

    if request.method == "POST" and form.is_valid():
        emp = form.save()

        if emp.dispositivo:
            disp = emp.dispositivo

            ud = (UsuarioDispositivo.objects
                  .filter(dispositivo=disp)
                  .filter(Q(user_id=emp.user_id or ""))
                  .first())

            if ud:
                ud.user_id = emp.user_id or ud.user_id
                ud.nombre = emp.nombre_completo[:64]
                ud.activo = emp.activo
                ud.empleado = emp
                ud.save(update_fields=["user_id", "nombre", "activo", "empleado"])
            else:
                UsuarioDispositivo.objects.create(
                    dispositivo=disp,
                    uid=emp.uid,  # None / 0
                    user_id=emp.user_id or "",
                    nombre=emp.nombre_completo[:64],
                    activo=emp.activo,
                    empleado=emp,
                )

        messages.success(request, "Empleado actualizado.")
        return redirect("empleados:list")

    return render(request, "empleados/empleado_form.html", {"form": form, "modo": "editar", "obj": emp})


# ======================
#  VINCULAR EMPLEADO
# ======================
@login_required
@user_passes_test(_only_staff)
@require_http_methods(["GET", "POST"])
@transaction.atomic
def empleado_vincular(request, pk):
    emp = get_object_or_404(Empleado, pk=pk)
    data = request.POST if request.method == "POST" else request.GET
    form = VincularUsuarioForm(data or None, empleado=emp)

    if request.method == "POST" and form.is_valid():
        ud = form.cleaned_data["usuario"]

        # Tomamos el user_id/uid existentes del usuario del equipo
        emp.uid = emp.uid or ud.uid
        if not emp.user_id:
            emp.user_id = ud.user_id or _siguiente_user_id(ud.dispositivo)
        if not emp.dispositivo_id:
            emp.dispositivo = ud.dispositivo
        emp.save(update_fields=["uid", "user_id", "dispositivo"])

        ud.empleado = emp
        ud.nombre = emp.nombre_completo[:64]
        ud.activo = emp.activo
        ud.save(update_fields=["empleado", "nombre", "activo"])

        messages.success(request, "Vinculado correctamente.")
        return redirect("empleados:editar", pk=emp.pk)

    return render(request, "empleados/empleado_vincular.html", {"form": form, "emp": emp})

@login_required
@user_passes_test(_only_staff)
@require_http_methods(["POST"])
@transaction.atomic
def empleado_crear_en_equipo(request, pk):
    emp = get_object_or_404(Empleado, pk=pk)

    # Determinar dispositivo
    if not emp.dispositivo_id:
        disp_id = request.POST.get("dispositivo_id")
        if not disp_id:
            messages.warning(request, "Seleccione un dispositivo.")
            return redirect("empleados:list")
        try:
            disp = Dispositivo.objects.get(pk=disp_id)
        except Dispositivo.DoesNotExist:
            messages.warning(request, "Dispositivo inválido.")
            return redirect("empleados:list")
    else:
        disp = emp.dispositivo

    # 1) Generar user_id (inicia en 200, salta de 10 en 10)
    user_val = emp.user_id or _siguiente_user_id(disp)

    # 2) Reservar user_id en BD (empleado=None)
    ud, _ = UsuarioDispositivo.objects.update_or_create(
        dispositivo=disp,
        user_id=user_val,
        defaults={
            "uid": emp.uid,
            "nombre": emp.nombre_completo[:64],
            "activo": emp.activo,
            "empleado": None,
        },
    )

    # 3) Insertar en el equipo
    try:
        conn, _ = _conn_with_fallbacks(disp)

        try: conn.disable_device()
        except: pass

        _sdk_set_user(
            conn,
            uid=0,
            user_id=user_val,
            name=emp.nombre_completo[:24],
            privilege=0,
            password="",
            group_id="0",
            card=0,
        )

        try: conn.refresh_data()
        except: pass

        try: conn.enable_device()
        except: pass

        conn.disconnect()

    except Exception as e:
        messages.warning(
            request,
            f"Fallo al registrar en equipo: {type(e).__name__}: {e}"
        )
        return redirect("empleados:list")

    # 4) Si el alta fue correcta, ahora sí vinculamos
    cambios = []
    if emp.user_id != user_val:
        emp.user_id = user_val
        cambios.append("user_id")

    if emp.dispositivo_id != disp.id:
        emp.dispositivo = disp
        cambios.append("dispositivo")

    if cambios:
        emp.save(update_fields=cambios)

    ud.empleado = emp
    ud.nombre = emp.nombre_completo[:64]
    ud.activo = emp.activo
    ud.save(update_fields=["empleado", "nombre", "activo"])

    messages.success(request, "Registrado en el equipo y vinculado.")
    return redirect("empleados:list")


# ======================
#  DOCUMENTOS (Upload)
# ======================
@login_required
@user_passes_test(_only_staff)
def documento_subir_empleado(request, emp_id):
    if request.method == "POST":
        obj = get_object_or_404(Empleado, pk=emp_id)
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.empleado = obj
            doc.save()
            messages.success(request, "Documento subido.")
        else:
            messages.error(request, "Error al subir documento.")
        return redirect("empleados:detalle", pk=emp_id)
    return redirect("empleados:list")

@login_required
@user_passes_test(_only_staff)
def documento_subir_candidato(request, cand_id):
    if request.method == "POST":
        obj = get_object_or_404(Candidato, pk=cand_id)
        form = DocumentoForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.candidato = obj
            doc.save()
            messages.success(request, "Documento subido.")
        else:
            messages.error(request, "Error al subir documento.")
        return redirect("empleados:candidato_detalle", pk=cand_id)
    return redirect("empleados:candidato_list")

@login_required
@user_passes_test(_only_staff)
def documento_eliminar(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    emp_id = doc.empleado_id
    cand_id = doc.candidato_id
    doc.delete()
    messages.success(request, "Documento eliminado.")
    if emp_id:
        return redirect("empleados:detalle", pk=emp_id)
    if cand_id:
        return redirect("empleados:candidato_detalle", pk=cand_id)
    return redirect("empleados:list")


# ======================
#  CANTERA (Candidatos)
# ======================
@login_required
@user_passes_test(_only_staff)
def candidato_list(request):
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("estado")

    qs = Candidato.objects.all().order_by("-creado_en")

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q) |
            Q(doc_id__icontains=q) |
            Q(skills__icontains=q)
        )
    if status and status in dict(Candidato.ESTADOS):
        qs = qs.filter(estado=status)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "empleados/candidato_list.html", {
        "page_obj": page_obj, "q": q, "estado": status, "estados": Candidato.ESTADOS
    })

@login_required
@user_passes_test(_only_staff)
def candidato_detalle(request, pk):
    obj = get_object_or_404(Candidato, pk=pk)
    documentos = obj.documentos.order_by("-subido_en")
    doc_form = DocumentoForm()
    return render(request, "empleados/candidato_detail.html", {
        "obj": obj,
        "documentos": documentos,
        "doc_form": doc_form
    })

@login_required
@user_passes_test(_only_staff)
def candidato_crear(request):
    form = CandidatoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save()
        messages.success(request, "Candidato registrado.")
        return redirect("empleados:candidato_list")
    return render(request, "empleados/candidato_form.html", {"form": form, "modo": "crear"})

@login_required
@user_passes_test(_only_staff)
def candidato_editar(request, pk):
    obj = get_object_or_404(Candidato, pk=pk)
    form = CandidatoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Candidato actualizado.")
        return redirect("empleados:candidato_list")
    return render(request, "empleados/candidato_form.html", {"form": form, "modo": "editar", "obj": obj})

@login_required
@user_passes_test(_only_staff)
def candidato_promover(request, pk):
    candidato = get_object_or_404(Candidato, pk=pk)
    # Pre-llenar form de empleado
    initial = {
        "nombre": candidato.nombre,
        "apellido": candidato.apellido,
        "doc_id": candidato.doc_id,
        "telefono": candidato.telefono,
        "email": candidato.email,
        #"tipo_vinculacion": "CONT", # Default a contratado
    }
    form = EmpleadoForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        emp = form.save()
        # Actualizar estado candidato
        candidato.estado = "CONTR"
        candidato.save()
        messages.success(request, f"Candidato promovido a empleado: {emp}")
        return redirect("empleados:list")

    return render(request, "empleados/candidato_promover.html", {"form": form, "candidato": candidato})


@login_required
@user_passes_test(_only_staff)
def baja_crear(request, emp_id):
    emp = get_object_or_404(Empleado, pk=emp_id)
    form = BajaAutorizadaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        baja = form.save(commit=False)
        baja.empleado = emp
        baja.save()
        messages.success(request, f"Baja autorizada registrada para {emp}.")
        return redirect("empleados:detalle", pk=emp_id)
    
    return render(request, "empleados/baja_form.html", {"form": form, "emp": emp})


@login_required
@user_passes_test(_only_staff)
def baja_eliminar(request, pk):
    baja = get_object_or_404(BajaAutorizada, pk=pk)
    emp_id = baja.empleado_id
    baja.delete()
@login_required
@user_passes_test(_only_staff)
def empleado_vincular(request, pk):
    emp = get_object_or_404(Empleado, pk=pk)
    
    if request.method == "POST":
        form = LinkUsuarioDispositivoForm(request.POST)
        if form.is_valid():
            # usuario is a ModelChoiceField, so it returns the UsuarioDispositivo object
            ud = form.cleaned_data["usuario"]
            # Enforce single link per UsuarioDispositivo? Or overwrite?
            # Model says ForeignKey(Empleado), so one UsuarioDispositivo -> one Empleado.
            # But one Empleado <-> many UsuarioDispositivo (related_name="usuarios_dispositivo")
            
            ud.empleado = emp
            ud.save()
            messages.success(request, f"Dispositivo vinculado: {ud.dispositivo.nombre} - {ud.nombre or ud.user_id}")
            return redirect("empleados:detalle", pk=pk)
    else:
        form = LinkUsuarioDispositivoForm()

    return render(request, "empleados/empleado_vincular.html", {"form": form, "emp": emp})


@login_required
def load_users(request):
    dispositivo_id = request.GET.get('dispositivo')
    users = UsuarioDispositivo.objects.none()
    if dispositivo_id:
        users = UsuarioDispositivo.objects.filter(dispositivo_id=dispositivo_id).order_by('nombre', 'user_id')
    
    return render(request, "empleados/dropdown_users.html", {"users": users})


@login_required
@user_passes_test(_only_staff)
@require_http_methods(["POST"])
def empleado_desvincular(request, pk):
    # pk del UsuarioDispositivo a desvincular
    ud = get_object_or_404(UsuarioDispositivo, pk=pk)
    emp_id = ud.empleado_id
    
    ud.empleado = None
    ud.save()
    
    messages.success(request, f"Desvinculado del dispositivo: {ud.dispositivo.nombre}")
    
    if emp_id:
        return redirect("empleados:detalle", pk=emp_id)
    return redirect("empleados:list")
