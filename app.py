"""
Torre de Control FTTH — Somos Internet
Flask backend con roles: coordinador y técnico
"""

import os, re, json
from datetime import datetime, date, timedelta
from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, abort)
from flask_sqlalchemy import SQLAlchemy

# ─── App setup ────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ftth-torre-control-2026-secreto')

raw_db = os.environ.get('DATABASE_URL', 'sqlite:///torre_control.db')
# Render usa postgres://, SQLAlchemy necesita postgresql://
if raw_db.startswith('postgres://'):
    raw_db = raw_db.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── Modelos ──────────────────────────────────────────

class Tecnico(db.Model):
    __tablename__ = 'tecnicos'
    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(100), nullable=False)
    zona        = db.Column(db.String(60))
    telefono    = db.Column(db.String(20))
    slack_id    = db.Column(db.String(20))
    activo      = db.Column(db.Boolean, default=True)
    creado      = db.Column(db.DateTime, default=datetime.utcnow)
    tickets     = db.relationship('Ticket', backref='tecnico_rel', lazy=True)

    def to_dict(self):
        tickets_mes = Ticket.query.filter(
            Ticket.tecnico_id == self.id,
            Ticket.fecha_apertura >= datetime.utcnow().replace(day=1)
        ).count()
        en_curso = Ticket.query.filter(
            Ticket.tecnico_id == self.id,
            Ticket.estado.in_(['EN_TRANSITO', 'EN_SITIO'])
        ).count()
        return {
            'id': self.id, 'nombre': self.nombre, 'zona': self.zona,
            'telefono': self.telefono, 'slack_id': self.slack_id,
            'activo': self.activo, 'tickets_mes': tickets_mes, 'en_curso': en_curso
        }


class Ticket(db.Model):
    __tablename__ = 'tickets'
    id              = db.Column(db.Integer, primary_key=True)
    slack_num       = db.Column(db.String(20))
    site            = db.Column(db.String(120), nullable=False)
    torre           = db.Column(db.String(40))
    acc_nombre      = db.Column(db.String(120))
    acc_ip          = db.Column(db.String(20))
    edge_nombre     = db.Column(db.String(120))
    edge_ip         = db.Column(db.String(20))
    modelo          = db.Column(db.String(20))
    tipo            = db.Column(db.String(80))
    afectados       = db.Column(db.Integer, default=0)
    observacion     = db.Column(db.Text)
    macs            = db.Column(db.Text)           # JSON string
    topologia_url   = db.Column(db.String(300))
    ubicacion_url   = db.Column(db.String(300))
    appointment_num = db.Column(db.String(20))
    estado          = db.Column(db.String(20), default='ABIERTO')
    semaforo        = db.Column(db.String(10), default='VERDE')
    es_reincidente  = db.Column(db.Boolean, default=False)
    evento_num      = db.Column(db.Integer, default=1)
    tecnico_id      = db.Column(db.Integer, db.ForeignKey('tecnicos.id'), nullable=True)
    fecha_apertura  = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_asignacion= db.Column(db.DateTime)
    fecha_llegada   = db.Column(db.DateTime)
    fecha_cierre    = db.Column(db.DateTime)
    raw_mensaje     = db.Column(db.Text)
    cierre          = db.relationship('Cierre', backref='ticket', uselist=False, lazy=True)

    @property
    def mttr_minutos(self):
        if self.fecha_apertura and self.fecha_cierre:
            return int((self.fecha_cierre - self.fecha_apertura).total_seconds() / 60)
        return None

    def to_dict(self):
        tec = self.tecnico_rel
        return {
            'id': self.id,
            'slack_num': self.slack_num,
            'site': self.site,
            'torre': self.torre,
            'acc_nombre': self.acc_nombre,
            'acc_ip': self.acc_ip,
            'edge_nombre': self.edge_nombre,
            'edge_ip': self.edge_ip,
            'modelo': self.modelo,
            'tipo': self.tipo,
            'afectados': self.afectados,
            'observacion': self.observacion,
            'macs': json.loads(self.macs) if self.macs else [],
            'topologia_url': self.topologia_url,
            'ubicacion_url': self.ubicacion_url,
            'appointment_num': self.appointment_num,
            'estado': self.estado,
            'semaforo': self.semaforo,
            'es_reincidente': self.es_reincidente,
            'evento_num': self.evento_num,
            'tecnico_id': self.tecnico_id,
            'tecnico_nombre': tec.nombre if tec else None,
            'fecha_apertura': self.fecha_apertura.isoformat() if self.fecha_apertura else None,
            'fecha_asignacion': self.fecha_asignacion.isoformat() if self.fecha_asignacion else None,
            'fecha_llegada': self.fecha_llegada.isoformat() if self.fecha_llegada else None,
            'fecha_cierre': self.fecha_cierre.isoformat() if self.fecha_cierre else None,
            'mttr_minutos': self.mttr_minutos,
            'cierre': self.cierre.to_dict() if self.cierre else None,
        }


class Cierre(db.Model):
    __tablename__ = 'cierres'
    id              = db.Column(db.Integer, primary_key=True)
    ticket_id       = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    tecnico_id      = db.Column(db.Integer, db.ForeignKey('tecnicos.id'))
    causa_raiz      = db.Column(db.String(120))
    clasificacion   = db.Column(db.String(80))
    acciones        = db.Column(db.Text)       # JSON list
    estado_acc      = db.Column(db.String(40))
    estado_edge     = db.Column(db.String(40))
    estado_switch   = db.Column(db.String(40))
    potencia_dbm    = db.Column(db.Float)
    solucion        = db.Column(db.Text)
    estado_final    = db.Column(db.String(20))
    escalamiento    = db.Column(db.String(80))
    riesgo          = db.Column(db.Boolean, default=False)
    desc_riesgo     = db.Column(db.Text)
    recomendacion   = db.Column(db.Text)
    creado          = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'causa_raiz': self.causa_raiz,
            'clasificacion': self.clasificacion,
            'acciones': json.loads(self.acciones) if self.acciones else [],
            'estado_acc': self.estado_acc,
            'estado_edge': self.estado_edge,
            'estado_switch': self.estado_switch,
            'potencia_dbm': self.potencia_dbm,
            'solucion': self.solucion,
            'estado_final': self.estado_final,
            'escalamiento': self.escalamiento,
            'recomendacion': self.recomendacion,
        }


class Actividad(db.Model):
    __tablename__ = 'actividad'
    id          = db.Column(db.Integer, primary_key=True)
    texto       = db.Column(db.String(200))
    tipo        = db.Column(db.String(20))   # new|assign|closed|alert
    ticket_id   = db.Column(db.Integer)
    usuario     = db.Column(db.String(80))
    fecha       = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'texto': self.texto, 'tipo': self.tipo,
            'ticket_id': self.ticket_id, 'usuario': self.usuario,
            'fecha': self.fecha.isoformat()
        }


# ─── Helpers ──────────────────────────────────────────

def log_actividad(texto, tipo, ticket_id=None, usuario=None):
    act = Actividad(texto=texto, tipo=tipo, ticket_id=ticket_id, usuario=usuario)
    db.session.add(act)


def evaluar_reincidencia(ticket):
    """Evalúa las 8 reglas de negocio y asigna semáforo al ticket."""
    inicio_mes = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    eventos_site = Ticket.query.filter(
        Ticket.site == ticket.site,
        Ticket.torre == ticket.torre,
        Ticket.fecha_apertura >= inicio_mes,
        Ticket.id != ticket.id
    ).count() + 1

    ticket.evento_num = eventos_site

    if eventos_site >= 3:
        ticket.semaforo = 'ROJO'
        ticket.es_reincidente = True
    elif eventos_site >= 2:
        ticket.semaforo = 'AMARILLO'
        ticket.es_reincidente = True
    else:
        # Revisar si el ACC ya tuvo eventos
        eventos_acc = Ticket.query.filter(
            Ticket.acc_ip == ticket.acc_ip,
            Ticket.fecha_apertura >= inicio_mes,
            Ticket.id != ticket.id
        ).count()
        if eventos_acc >= 1:
            ticket.semaforo = 'AMARILLO'
            ticket.es_reincidente = True
        else:
            ticket.semaforo = 'VERDE'
            ticket.es_reincidente = False


def parse_slack_message(texto):
    """Parsea un mensaje de Slack con formato de ticket FTTH."""
    data = {}
    lines = [l.strip() for l in texto.split('\n') if l.strip()]

    for i, line in enumerate(lines):
        # Ticket number
        m = re.search(r'Ticket\s*#?(\d+)', line, re.I)
        if m: data['slack_num'] = m.group(1)

        # Edge nombre + IP en misma línea
        m = re.search(r'Edge/ACC\s+(COL_\S+)\s+-\s+([\d.]+)', line, re.I)
        if m:
            data['edge_nombre'] = m.group(1)
            data['edge_ip']     = m.group(2)
            # Siguiente línea puede tener ACC
            if i + 1 < len(lines):
                m2 = re.search(r'^(COL_\S+ACC\S*)\s+-\s+([\d.]+)', lines[i+1])
                if m2:
                    data['acc_nombre'] = m2.group(1)
                    data['acc_ip']     = m2.group(2)

        # Solo Edge
        m = re.search(r'^(COL_\S+EDGE\S*)\s+-\s+([\d.]+)', line, re.I)
        if m and 'edge_nombre' not in data:
            data['edge_nombre'] = m.group(1)
            data['edge_ip']     = m.group(2)

        # Solo ACC
        m = re.search(r'^(COL_\S+ACC\S*)\s+-\s+([\d.]+)', line, re.I)
        if m and 'acc_nombre' not in data:
            data['acc_nombre'] = m.group(1)
            data['acc_ip']     = m.group(2)

        # Nombre del sitio
        if re.search(r'nombre del sitio', line, re.I):
            next_line = lines[i+1] if i+1 < len(lines) else ''
            # Puede estar en la misma línea después de ":"
            m = re.search(r'nombre del sitio:?\s*(.+)', line, re.I)
            if m and m.group(1).strip():
                data['site'] = m.group(1).strip()
            elif next_line and not re.match(r'^(Torre|Modelo|#)', next_line, re.I):
                data['site'] = next_line

        # Torre
        m = re.search(r'Torre\s+(\d+)', line, re.I)
        if m: data['torre'] = f"Torre {m.group(1)}"

        # Modelo
        if re.search(r'modelo\s+equipo', line, re.I):
            nxt = lines[i+1] if i+1 < len(lines) else ''
            if nxt and len(nxt) < 20: data['modelo'] = nxt

        # Afectados
       if re.search(r'#\s*afectados', line, re.I) and 'afectados' not in data:
            m = re.search(r'#\s*[Aa]fectados\s*:?\s*(\d+)', line)
            if m:
                data['afectados'] = int(m.group(1))
            else:
                nxt = lines[i+1] if i+1 < len(lines) else ''
                m2 = re.search(r'(\d+)', nxt)
                if m2: data['afectados'] = int(m2.group(1))

        # Tipo de problema
    if re.search(r'tipo de problema', line, re.I) and 'tipo' not in data:
            m = re.search(r'[Tt]ipo\s+de\s+[Pp]roblema:?\s*(.+)', line)
            if m and m.group(1).strip():
                data['tipo'] = m.group(1).strip()
            else:
                nxt = lines[i+1] if i+1 < len(lines) else ''
                if nxt and len(nxt) < 60:
                    data['tipo'] = nxt

        # MACs
        m = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line, re.I)
        if m:
            apt = re.search(r'APT\s*(\d+)', line, re.I)
            if 'macs' not in data: data['macs'] = []
            data['macs'].append({'mac': m.group(1), 'apt': apt.group(1) if apt else None})

        # Appointment
        m = re.search(r'Appointment\s*#?(\d+)', line, re.I)
        if m: data['appointment_num'] = m.group(1)

        # URLs
        m = re.search(r'(https?://\S+)', line)
        if m:
            url = m.group(1)
            ctx = line.lower() + (lines[i-1].lower() if i > 0 else '')
            if 'drive' in ctx or 'topolog' in ctx:
                data['topologia_url'] = url
            elif 'map' in ctx or 'ubicac' in ctx:
                data['ubicacion_url'] = url

    # Observación
    m = re.search(r'Observaci[oó]n:?\n([\s\S]+?)(?:\n(?:Usuario|Topolog|Ubicac|Técnico))', texto, re.I)
    if m: data['observacion'] = m.group(1).strip()

    return data


def require_login(roles=None):
    """Decorator simple de autenticación por sesión."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'rol' not in session:
                return redirect(url_for('login'))
            if roles and session['rol'] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─── Rutas de autenticación ───────────────────────────

@app.route('/')
def index():
    if 'rol' in session:
        if session['rol'] == 'coordinador':
            return redirect(url_for('coordinador'))
        return redirect(url_for('tecnico'))
    return redirect(url_for('login'))


@app.route('/login')
def login():
    tecnicos = Tecnico.query.filter_by(activo=True).order_by(Tecnico.nombre).all()
    return render_template('login.html', tecnicos=tecnicos)


@app.route('/login', methods=['POST'])
def do_login():
    rol = request.form.get('rol')
    if rol == 'coordinador':
        pin = request.form.get('pin', '')
        pin_correcto = os.environ.get('COORDINADOR_PIN', '1234')
        if pin != pin_correcto:
            tecnicos = Tecnico.query.filter_by(activo=True).all()
            return render_template('login.html', tecnicos=tecnicos, error='PIN incorrecto')
        session['rol'] = 'coordinador'
        session['nombre'] = 'Coordinador'
        session['tecnico_id'] = None
        return redirect(url_for('coordinador'))
    elif rol == 'tecnico':
        tec_id = request.form.get('tecnico_id')
        tec = Tecnico.query.get(tec_id)
        if not tec or not tec.activo:
            tecnicos = Tecnico.query.filter_by(activo=True).all()
            return render_template('login.html', tecnicos=tecnicos, error='Técnico no encontrado')
        session['rol'] = 'tecnico'
        session['tecnico_id'] = tec.id
        session['nombre'] = tec.nombre
        return redirect(url_for('tecnico'))
    return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─── Vistas principales ───────────────────────────────

@app.route('/coordinador')
@require_login(['coordinador'])
def coordinador():
    return render_template('coordinador.html', nombre=session['nombre'])


@app.route('/tecnico')
@require_login(['tecnico'])
def tecnico():
    tec = Tecnico.query.get(session['tecnico_id'])
    return render_template('tecnico.html', tecnico=tec, nombre=session['nombre'])


# ─── API: Tickets ─────────────────────────────────────

@app.route('/api/tickets', methods=['GET'])
@require_login()
def get_tickets():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    estado = request.args.get('estado')
    tec_id = request.args.get('tecnico_id')

    q = Ticket.query

    # Técnico solo ve los suyos
    if session['rol'] == 'tecnico':
        q = q.filter(Ticket.tecnico_id == session['tecnico_id'])
    elif tec_id:
        q = q.filter(Ticket.tecnico_id == int(tec_id))

    if desde:
        q = q.filter(Ticket.fecha_apertura >= datetime.fromisoformat(desde))
    if hasta:
        hasta_dt = datetime.fromisoformat(hasta) + timedelta(days=1)
        q = q.filter(Ticket.fecha_apertura < hasta_dt)
    if estado and estado != 'all':
        q = q.filter(Ticket.estado == estado)

    tickets = q.order_by(Ticket.fecha_apertura.desc()).all()
    return jsonify([t.to_dict() for t in tickets])


@app.route('/api/tickets', methods=['POST'])
@require_login(['coordinador'])
def crear_ticket():
    data = request.json or {}
    raw = data.get('raw_mensaje', '')

    # Si viene mensaje crudo de Slack, parsearlo
    if raw:
        parsed = parse_slack_message(raw)
        data.update({k: v for k, v in parsed.items() if k not in data or not data[k]})

    if not data.get('site'):
        return jsonify({'error': 'El campo site es obligatorio'}), 400

    t = Ticket(
        slack_num       = data.get('slack_num'),
        site            = data['site'],
        torre           = data.get('torre', 'Torre 1'),
        acc_nombre      = data.get('acc_nombre'),
        acc_ip          = data.get('acc_ip'),
        edge_nombre     = data.get('edge_nombre'),
        edge_ip         = data.get('edge_ip'),
        modelo          = data.get('modelo'),
        tipo            = data.get('tipo', 'Ausencia de Servicio'),
        afectados       = int(data.get('afectados', 0)),
        observacion     = data.get('observacion'),
        macs            = json.dumps(data.get('macs', [])),
        topologia_url   = data.get('topologia_url'),
        ubicacion_url   = data.get('ubicacion_url'),
        appointment_num = data.get('appointment_num'),
        raw_mensaje     = raw or None,
        fecha_apertura  = datetime.utcnow(),
    )
    db.session.add(t)
    db.session.flush()
    evaluar_reincidencia(t)
    log_actividad(
        f"Nuevo ticket #{t.slack_num or t.id} — {t.site} {t.torre}",
        'new', t.id, session.get('nombre')
    )
    db.session.commit()
    return jsonify(t.to_dict()), 201


@app.route('/api/tickets/<int:tid>', methods=['GET'])
@require_login()
def get_ticket(tid):
    t = Ticket.query.get_or_404(tid)
    if session['rol'] == 'tecnico' and t.tecnico_id != session['tecnico_id']:
        abort(403)
    return jsonify(t.to_dict())


@app.route('/api/tickets/<int:tid>/asignar', methods=['PUT'])
@require_login(['coordinador'])
def asignar_ticket(tid):
    t = Ticket.query.get_or_404(tid)
    data = request.json or {}
    tec_id = data.get('tecnico_id')
    tec = Tecnico.query.get_or_404(tec_id)

    t.tecnico_id = tec.id
    t.estado = 'EN_TRANSITO'
    t.fecha_asignacion = datetime.utcnow()

    log_actividad(
        f"{tec.nombre} asignado a #{t.slack_num or t.id} — {t.site}",
        'assign', t.id, session.get('nombre')
    )
    db.session.commit()
    return jsonify(t.to_dict())


@app.route('/api/tickets/<int:tid>/en-sitio', methods=['PUT'])
@require_login()
def marcar_en_sitio(tid):
    t = Ticket.query.get_or_404(tid)
    if session['rol'] == 'tecnico' and t.tecnico_id != session['tecnico_id']:
        abort(403)
    t.estado = 'EN_SITIO'
    t.fecha_llegada = datetime.utcnow()
    log_actividad(f"Técnico llegó a sitio — #{t.slack_num or t.id} {t.site}", 'assign', t.id, session.get('nombre'))
    db.session.commit()
    return jsonify(t.to_dict())


@app.route('/api/tickets/<int:tid>/cerrar', methods=['POST'])
@require_login()
def cerrar_ticket(tid):
    t = Ticket.query.get_or_404(tid)
    if session['rol'] == 'tecnico' and t.tecnico_id != session['tecnico_id']:
        abort(403)

    data = request.json or {}
    required = ['causa_raiz', 'clasificacion', 'acciones', 'solucion', 'estado_final']
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Campos obligatorios faltantes: {", ".join(missing)}'}), 400
    if len(data.get('solucion', '')) < 50:
        return jsonify({'error': 'La solución debe tener mínimo 50 caracteres'}), 400
    if not data.get('acciones'):
        return jsonify({'error': 'Debes registrar al menos una acción realizada'}), 400

    cierre = Cierre(
        ticket_id     = t.id,
        tecnico_id    = session.get('tecnico_id') or t.tecnico_id,
        causa_raiz    = data['causa_raiz'],
        clasificacion = data['clasificacion'],
        acciones      = json.dumps(data['acciones']),
        estado_acc    = data.get('estado_acc'),
        estado_edge   = data.get('estado_edge'),
        estado_switch = data.get('estado_switch'),
        potencia_dbm  = data.get('potencia_dbm'),
        solucion      = data['solucion'],
        estado_final  = data['estado_final'],
        escalamiento  = data.get('escalamiento'),
        riesgo        = bool(data.get('riesgo')),
        desc_riesgo   = data.get('desc_riesgo'),
        recomendacion = data.get('recomendacion'),
    )
    db.session.add(cierre)

    estado_final = data['estado_final']
    t.estado = estado_final
    t.fecha_cierre = datetime.utcnow()

    if 'repetitiva' in data['clasificacion'].lower():
        t.es_reincidente = True

    tipo_act = 'closed' if estado_final == 'CERRADO' else 'alert'
    log_actividad(
        f"Ticket #{t.slack_num or t.id} {estado_final.lower()} — {t.site} | {data['causa_raiz']}",
        tipo_act, t.id, session.get('nombre')
    )
    db.session.commit()
    return jsonify(t.to_dict())


# ─── API: Técnicos ────────────────────────────────────

@app.route('/api/tecnicos', methods=['GET'])
@require_login()
def get_tecnicos():
    tecnicos = Tecnico.query.order_by(Tecnico.nombre).all()
    return jsonify([t.to_dict() for t in tecnicos])


@app.route('/api/tecnicos', methods=['POST'])
@require_login(['coordinador'])
def crear_tecnico():
    data = request.json or {}
    if not data.get('nombre'):
        return jsonify({'error': 'El nombre es obligatorio'}), 400
    t = Tecnico(
        nombre   = data['nombre'],
        zona     = data.get('zona'),
        telefono = data.get('telefono'),
        slack_id = data.get('slack_id'),
        activo   = True,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@app.route('/api/tecnicos/<int:tid>', methods=['PUT'])
@require_login(['coordinador'])
def actualizar_tecnico(tid):
    t = Tecnico.query.get_or_404(tid)
    data = request.json or {}
    for field in ['nombre', 'zona', 'telefono', 'slack_id', 'activo']:
        if field in data:
            setattr(t, field, data[field])
    db.session.commit()
    return jsonify(t.to_dict())


@app.route('/api/tecnicos/<int:tid>', methods=['DELETE'])
@require_login(['coordinador'])
def desactivar_tecnico(tid):
    t = Tecnico.query.get_or_404(tid)
    t.activo = False
    db.session.commit()
    return jsonify({'ok': True})


# ─── API: KPIs y actividad ────────────────────────────

@app.route('/api/kpis')
@require_login(['coordinador'])
def get_kpis():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    q = Ticket.query
    if desde:
        q = q.filter(Ticket.fecha_apertura >= datetime.fromisoformat(desde))
    if hasta:
        hasta_dt = datetime.fromisoformat(hasta) + timedelta(days=1)
        q = q.filter(Ticket.fecha_apertura < hasta_dt)

    tickets = q.all()
    total        = len(tickets)
    abiertos     = sum(1 for t in tickets if t.estado == 'ABIERTO')
    sin_asignar  = sum(1 for t in tickets if t.estado == 'ABIERTO' and not t.tecnico_id)
    en_transito  = sum(1 for t in tickets if t.estado == 'EN_TRANSITO')
    en_sitio     = sum(1 for t in tickets if t.estado == 'EN_SITIO')
    cerrados     = sum(1 for t in tickets if t.estado == 'CERRADO')
    afectados    = sum(t.afectados for t in tickets if t.estado != 'CERRADO')
    reincidentes = sum(1 for t in tickets if t.es_reincidente)
    sites_rojo   = len(set(f"{t.site} {t.torre}" for t in tickets if t.semaforo == 'ROJO'))

    closed_no_reinc = sum(1 for t in tickets if t.estado == 'CERRADO' and not t.es_reincidente)
    fcr = round(closed_no_reinc / cerrados * 100) if cerrados > 0 else 0

    mttrs = [t.mttr_minutos for t in tickets if t.mttr_minutos]
    mttr  = round(sum(mttrs) / len(mttrs)) if mttrs else None

    # Sites
    site_counts = {}
    for t in tickets:
        k = f"{t.site} {t.torre}"
        if k not in site_counts:
            site_counts[k] = {'count': 0, 'semaforo': t.semaforo}
        site_counts[k]['count'] += 1
        if t.semaforo == 'ROJO':
            site_counts[k]['semaforo'] = 'ROJO'
        elif t.semaforo == 'AMARILLO' and site_counts[k]['semaforo'] != 'ROJO':
            site_counts[k]['semaforo'] = 'AMARILLO'

    # Tipos de falla
    falla_counts = {}
    for t in tickets:
        if t.tipo:
            falla_counts[t.tipo] = falla_counts.get(t.tipo, 0) + 1

    return jsonify({
        'total': total, 'abiertos': abiertos, 'sin_asignar': sin_asignar,
        'en_transito': en_transito, 'en_sitio': en_sitio, 'cerrados': cerrados,
        'afectados': afectados, 'reincidentes': reincidentes,
        'sites_rojo': sites_rojo, 'fcr': fcr, 'mttr': mttr,
        'tasa_reinc': round(reincidentes / total * 100) if total > 0 else 0,
        'sites': sorted(site_counts.items(), key=lambda x: -x[1]['count'])[:8],
        'fallas': sorted(falla_counts.items(), key=lambda x: -x[1])[:8],
    })


@app.route('/api/actividad')
@require_login()
def get_actividad():
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    q = Actividad.query
    if desde:
        q = q.filter(Actividad.fecha >= datetime.fromisoformat(desde))
    if hasta:
        hasta_dt = datetime.fromisoformat(hasta) + timedelta(days=1)
        q = q.filter(Actividad.fecha < hasta_dt)
    acts = q.order_by(Actividad.fecha.desc()).limit(30).all()
    return jsonify([a.to_dict() for a in acts])


# ─── Webhook Slack ────────────────────────────────────

@app.route('/webhook/slack', methods=['POST'])
def webhook_slack():
    """
    Recibe mensajes de Slack via Make.com o Zapier.
    Make.com: POST con body { "text": "mensaje del canal" }
    """
    # Verificar token básico
    token = request.headers.get('X-Webhook-Token', '')
    expected = os.environ.get('WEBHOOK_TOKEN', 'mi-token-secreto')
    if token != expected:
        return jsonify({'error': 'Token inválido'}), 401

    data = request.json or {}
    texto = data.get('text', '') or data.get('message', '')

    if not texto or 'Ticket' not in texto:
        return jsonify({'skipped': True}), 200

    parsed = parse_slack_message(texto)
    if not parsed.get('site'):
        return jsonify({'skipped': True, 'reason': 'No se pudo extraer site'}), 200

    t = Ticket(
        slack_num       = parsed.get('slack_num'),
        site            = parsed.get('site', 'Sin nombre'),
        torre           = parsed.get('torre', 'Torre 1'),
        acc_nombre      = parsed.get('acc_nombre'),
        acc_ip          = parsed.get('acc_ip'),
        edge_nombre     = parsed.get('edge_nombre'),
        edge_ip         = parsed.get('edge_ip'),
        modelo          = parsed.get('modelo'),
        tipo            = parsed.get('tipo', 'Ausencia de Servicio'),
        afectados       = int(parsed.get('afectados', 0)),
        observacion     = parsed.get('observacion'),
        macs            = json.dumps(parsed.get('macs', [])),
        topologia_url   = parsed.get('topologia_url'),
        ubicacion_url   = parsed.get('ubicacion_url'),
        appointment_num = parsed.get('appointment_num'),
        raw_mensaje     = texto,
        fecha_apertura  = datetime.utcnow(),
    )
    db.session.add(t)
    db.session.flush()
    evaluar_reincidencia(t)
    log_actividad(
        f"Ticket #{t.slack_num or t.id} recibido desde Slack — {t.site} {t.torre}",
        'new', t.id, 'Slack Bot'
    )
    db.session.commit()
    return jsonify({'created': True, 'ticket_id': t.id}), 201


# ─── Init DB con datos semilla ────────────────────────

def seed_db():
    pass  # DB inicia limpia. Agrega tus tecnicos reales desde el panel Coordinador.


    
with app.app_context():
    db.create_all()
    seed_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
