# 🛰 Torre de Control FTTH — Sistema de Trazabilidad Operativa

**Empresa:** Somos Internet | **Versión:** 1.0 | **Stack:** Flask + SQLAlchemy + PostgreSQL

Sistema web completo para gestión de tickets de soporte técnico FTTH con roles diferenciados, trazabilidad total y detección automática de reincidencias.

---

## Roles del sistema

| Rol | Acceso | Funciones |
|---|---|---|
| **Coordinador** | PIN numérico | Dashboard completo, asignar tickets, ver todos los tickets, gestionar técnicos, registrar tickets manualmente |
| **Técnico** | Selecciona su nombre | Solo ve sus tickets asignados, marca llegada al sitio, cierra tickets con formulario completo |

---

## Cómo correr localmente

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/torre-control-ftth
cd torre-control-ftth

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tu editor y ajusta los valores

# 5. Correr la app
python app.py

# Abre tu navegador en: http://localhost:5000
```

### PIN por defecto para coordinador: `1234`
Cámbialo en el archivo `.env` con la variable `COORDINADOR_PIN`.

---

## Despliegue en Render.com (gratis)

### Opción A — Automática con render.yaml (recomendada)

1. Sube el repositorio a GitHub
2. Ve a [render.com](https://render.com) y crea una cuenta
3. Haz clic en **New → Blueprint**
4. Conecta tu repositorio de GitHub
5. Render detecta el `render.yaml` automáticamente y crea:
   - El servicio web Flask
   - La base de datos PostgreSQL
6. Configura las variables de entorno en el dashboard de Render:
   - `COORDINADOR_PIN` → tu PIN (ej: `4821`)
   - `WEBHOOK_TOKEN` → token secreto para Make.com

### Opción B — Manual

1. Sube a GitHub
2. En Render: **New → Web Service** → conecta el repo
3. Runtime: Python, Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app --workers 2 --timeout 120`
5. Agrega una base de datos: **New → PostgreSQL**
6. Copia el `Internal Database URL` y agrégalo como variable `DATABASE_URL`

---

## Cómo recibir tickets desde Slack automáticamente

### Configurar Make.com (sin código)

1. Crea cuenta en [make.com](https://make.com)
2. Crea nuevo escenario
3. **Módulo 1:** Slack → Watch Messages → Canal `C09E0415U5P`
4. **Módulo 2:** HTTP → Make a request
   - URL: `https://tu-app.onrender.com/webhook/slack`
   - Método: POST
   - Headers: `X-Webhook-Token: tu-token-secreto`
   - Body: `{"text": "{{1.text}}"}`
5. Activa el escenario

El bot detecta automáticamente mensajes con formato de ticket y extrae: site, torre, ACC, Edge, afectados, tipo, MACs, URLs de topología y ubicación.

### Si el ticket llega diferente o no lo captura

Ve a la pestaña **➕ Nuevo Ticket** en el dashboard del coordinador:
- **Opción A:** Pega el mensaje completo de Slack — el sistema lo parsea automáticamente
- **Opción B:** Llena el formulario campo por campo manualmente

---

## Estructura del proyecto

```
torre-control-ftth/
├── app.py                    # Backend Flask completo
├── requirements.txt          # Dependencias Python
├── Procfile                  # Comando de arranque para Render
├── render.yaml               # Configuración automática de Render
├── .env.example              # Plantilla de variables de entorno
├── .gitignore
├── README.md
├── templates/
│   ├── login.html            # Pantalla de login con selección de rol
│   ├── coordinador.html      # Dashboard completo del coordinador
│   └── tecnico.html          # Vista del técnico (solo sus tickets)
└── static/
    └── style.css             # Estilos dark theme compartidos
```

---

## Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/tickets` | Lista tickets (filtrado por rol automáticamente) |
| POST | `/api/tickets` | Crear ticket (manual o desde mensaje Slack) |
| PUT | `/api/tickets/<id>/asignar` | Asignar técnico a ticket |
| PUT | `/api/tickets/<id>/en-sitio` | Técnico marca llegada |
| POST | `/api/tickets/<id>/cerrar` | Cerrar ticket con formulario completo |
| GET | `/api/tecnicos` | Lista técnicos |
| POST | `/api/tecnicos` | Agregar técnico |
| PUT | `/api/tecnicos/<id>` | Editar técnico |
| DELETE | `/api/tecnicos/<id>` | Desactivar técnico |
| GET | `/api/kpis` | KPIs filtrados por fecha |
| GET | `/api/actividad` | Log de actividad |
| POST | `/webhook/slack` | Webhook para Make.com |

---

## Reglas de negocio — Motor de reincidencia

| Regla | Condición | Resultado |
|---|---|---|
| R1 | Site con ≥ 3 eventos/mes | Semáforo ROJO |
| R2 | ACC con ≥ 2 eventos/mes | Semáforo AMARILLO |
| R3 | Site con ≥ 2 eventos/mes | Semáforo AMARILLO + reincidente=true |
| R6 | Evento con > 10 afectados | Requiere atención inmediata |

---

## Agregar un técnico nuevo

1. Inicia sesión como **Coordinador**
2. Ve a la pestaña **👷 Técnicos**
3. Clic en **+ Agregar Técnico**
4. Completa nombre, zona y teléfono
5. El técnico ya puede iniciar sesión seleccionando su nombre

---

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave para sesiones Flask | Cadena aleatoria larga |
| `COORDINADOR_PIN` | PIN de acceso coordinador | `4821` |
| `DATABASE_URL` | URL de la base de datos | PostgreSQL URL de Render |
| `WEBHOOK_TOKEN` | Token para webhook de Slack | Cadena aleatoria |
| `FLASK_DEBUG` | Debug mode | `false` en producción |
