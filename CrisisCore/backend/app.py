from flask import Flask, request, jsonify
import sqlite3
import datetime
import os
import json

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        return jsonify({}), 200

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'crisis.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            location TEXT NOT NULL,
            room_number TEXT,
            description TEXT,
            reporter_name TEXT,
            reporter_phone TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS responders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT,
            phone TEXT,
            status TEXT DEFAULT 'available',
            current_incident_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS incident_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            responder_id INTEGER,
            message TEXT NOT NULL,
            update_type TEXT DEFAULT 'update',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id),
            FOREIGN KEY (responder_id) REFERENCES responders(id)
        );

        CREATE TABLE IF NOT EXISTS incident_responders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            responder_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id),
            FOREIGN KEY (responder_id) REFERENCES responders(id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER,
            message TEXT NOT NULL,
            alert_type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        );
    ''')

    # Seed responders if empty
    c.execute("SELECT COUNT(*) FROM responders")
    if c.fetchone()[0] == 0:
        responders = [
            ('James Harlow', 'Security Chief', 'Security', '+1-555-0101', 'available'),
            ('Maria Chen', 'Hotel Manager', 'Management', '+1-555-0102', 'available'),
            ('Dr. Priya Nair', 'Medical Officer', 'Medical', '+1-555-0103', 'available'),
            ('Tom Bradley', 'Fire Safety Officer', 'Fire Safety', '+1-555-0104', 'available'),
            ('Aisha Johnson', 'Guest Relations', 'Front Desk', '+1-555-0105', 'available'),
            ('Carlos Rivera', 'Security Guard', 'Security', '+1-555-0106', 'available'),
            ('Emma Walsh', 'Concierge', 'Front Desk', '+1-555-0107', 'available'),
            ('Raj Patel', 'Maintenance Head', 'Engineering', '+1-555-0108', 'available'),
        ]
        c.executemany("INSERT INTO responders (name, role, department, phone, status) VALUES (?,?,?,?,?)", responders)

    conn.commit()
    conn.close()

# ─── INCIDENTS ────────────────────────────────────────────────────────────────

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    conn = get_db()
    c = conn.cursor()
    status = request.args.get('status', None)
    if status:
        c.execute("SELECT * FROM incidents WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM incidents ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/incidents', methods=['POST'])
def create_incident():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO incidents (title, type, severity, location, room_number, description, reporter_name, reporter_phone)
                 VALUES (?,?,?,?,?,?,?,?)''',
              (data['title'], data['type'], data['severity'], data['location'],
               data.get('room_number',''), data.get('description',''),
               data.get('reporter_name','Guest'), data.get('reporter_phone','')))
    incident_id = c.lastrowid

    # Create alert
    severity_emoji = {'critical':'🚨','high':'⚠️','medium':'🔔','low':'ℹ️'}.get(data['severity'],'🔔')
    c.execute("INSERT INTO alerts (incident_id, message, alert_type) VALUES (?,?,?)",
              (incident_id, f"{severity_emoji} New {data['severity'].upper()} incident: {data['title']} at {data['location']}", data['severity']))

    # Auto-log creation
    c.execute("INSERT INTO incident_updates (incident_id, message, update_type) VALUES (?,?,?)",
              (incident_id, f"Incident reported by {data.get('reporter_name','Guest')}. Location: {data['location']}. {data.get('description','')}", 'created'))

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'incident_id': incident_id}), 201

@app.route('/api/incidents/<int:incident_id>', methods=['GET'])
def get_incident(incident_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM incidents WHERE id=?", (incident_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    incident = dict(row)

    c.execute('''SELECT r.* FROM responders r
                 JOIN incident_responders ir ON r.id = ir.responder_id
                 WHERE ir.incident_id=?''', (incident_id,))
    incident['responders'] = [dict(r) for r in c.fetchall()]

    c.execute("SELECT * FROM incident_updates WHERE incident_id=? ORDER BY created_at ASC", (incident_id,))
    incident['updates'] = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(incident)

@app.route('/api/incidents/<int:incident_id>/status', methods=['PUT'])
def update_incident_status(incident_id):
    data = request.json
    status = data.get('status')
    conn = get_db()
    c = conn.cursor()
    if status == 'resolved':
        c.execute("UPDATE incidents SET status=?, resolved_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, incident_id))
        c.execute("INSERT INTO incident_updates (incident_id, message, update_type) VALUES (?,?,?)",
                  (incident_id, "Incident has been resolved and closed.", 'resolved'))
        # Free assigned responders
        c.execute("SELECT responder_id FROM incident_responders WHERE incident_id=?", (incident_id,))
        for row in c.fetchall():
            c.execute("UPDATE responders SET status='available', current_incident_id=NULL WHERE id=?", (row[0],))
    else:
        c.execute("UPDATE incidents SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, incident_id))
        c.execute("INSERT INTO incident_updates (incident_id, message, update_type) VALUES (?,?,?)",
                  (incident_id, f"Incident status changed to: {status}", 'status_change'))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/incidents/<int:incident_id>/update', methods=['POST'])
def add_update(incident_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO incident_updates (incident_id, responder_id, message, update_type) VALUES (?,?,?,?)",
              (incident_id, data.get('responder_id'), data['message'], data.get('update_type','update')))
    conn.commit()
    conn.close()
    return jsonify({'success': True}), 201

@app.route('/api/incidents/<int:incident_id>/assign', methods=['POST'])
def assign_responder(incident_id):
    data = request.json
    responder_id = data['responder_id']
    conn = get_db()
    c = conn.cursor()
    # Check if already assigned
    c.execute("SELECT id FROM incident_responders WHERE incident_id=? AND responder_id=?", (incident_id, responder_id))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Already assigned'}), 400

    c.execute("INSERT INTO incident_responders (incident_id, responder_id) VALUES (?,?)", (incident_id, responder_id))
    c.execute("UPDATE responders SET status='on_duty', current_incident_id=? WHERE id=?", (incident_id, responder_id))
    c.execute("SELECT name, role FROM responders WHERE id=?", (responder_id,))
    r = c.fetchone()
    c.execute("INSERT INTO incident_updates (incident_id, responder_id, message, update_type) VALUES (?,?,?,?)",
              (incident_id, responder_id, f"{r['name']} ({r['role']}) has been assigned to this incident.", 'assignment'))
    conn.commit()
    conn.close()
    return jsonify({'success': True}), 201

# ─── RESPONDERS ───────────────────────────────────────────────────────────────

@app.route('/api/responders', methods=['GET'])
def get_responders():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM responders ORDER BY status, name")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

# ─── ALERTS ───────────────────────────────────────────────────────────────────

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 50")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/alerts/read', methods=['PUT'])
def mark_alerts_read():
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE alerts SET is_read=1")
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ─── STATS ────────────────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    c = conn.cursor()
    stats = {}
    c.execute("SELECT COUNT(*) FROM incidents WHERE status='active'")
    stats['active_incidents'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM incidents WHERE status='resolved'")
    stats['resolved_incidents'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM responders WHERE status='available'")
    stats['available_responders'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM responders WHERE status='on_duty'")
    stats['on_duty_responders'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM incidents WHERE severity='critical' AND status='active'")
    stats['critical_active'] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM alerts WHERE is_read=0")
    stats['unread_alerts'] = c.fetchone()[0]
    c.execute("""SELECT type, COUNT(*) as count FROM incidents
                 WHERE created_at >= datetime('now', '-30 days')
                 GROUP BY type ORDER BY count DESC""")
    stats['incident_types'] = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(stats)

# ─── QUICK SOS ────────────────────────────────────────────────────────────────

@app.route('/api/sos', methods=['POST'])
def sos():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO incidents (title, type, severity, location, room_number, description, reporter_name, reporter_phone)
                 VALUES (?,?,?,?,?,?,?,?)''',
              (f"SOS - {data.get('location','Unknown Location')}",
               data.get('type', 'emergency'), 'critical',
               data.get('location', 'Unknown'),
               data.get('room_number', ''),
               data.get('description', 'SOS signal triggered - immediate assistance required.'),
               data.get('name', 'Guest'),
               data.get('phone', '')))
    incident_id = c.lastrowid
    c.execute("INSERT INTO alerts (incident_id, message, alert_type) VALUES (?,?,?)",
              (incident_id, f"🆘 SOS SIGNAL from {data.get('location','Unknown')}! Room: {data.get('room_number','-')}. Immediate response required!", 'critical'))
    c.execute("INSERT INTO incident_updates (incident_id, message, update_type) VALUES (?,?,?)",
              (incident_id, "🆘 EMERGENCY SOS triggered. All available personnel must respond immediately.", 'sos'))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'incident_id': incident_id}), 201

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)