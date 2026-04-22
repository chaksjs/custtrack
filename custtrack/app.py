import os, io, json, smtplib, secrets, threading, random, time, base64
import pandas as pd
from datetime import datetime
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from flask import Flask, render_template, request, redirect, send_file, jsonify, session, url_for
from hdbcli import dbapi
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))

@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

# ── Config files ──────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
CONFIG_FILE  = os.path.join(BASE_DIR, 'hana_config.json')
STATS_FILE   = os.path.join(BASE_DIR, 'user_stats.json')

DEFAULT_HANA = {
    'host': '',
    'port': 443,
    'user': 'DBADMIN',
    'password': '',
    'admin_email': '',
    'support_email': '',
    'sender_email': '',
    'sender_password': '',
    'admin_password': '',
    'settings_users': [],
    'app_url': 'http://localhost:8080',
    'setup_complete': False
}

def _email_footer(app_url):
    return f"""
<div style="margin-top:32px; padding-top:16px; border-top:1px solid #e0e4ea; text-align:center; font-family:Arial,sans-serif;">
  <a href="{app_url}" style="display:inline-block; background:#008fd3; color:white; text-decoration:none;
     padding:10px 24px; border-radius:8px; font-weight:700; font-size:0.88rem; margin-bottom:14px;">
    🤝 Open CustTrack
  </a>
  <div style="font-size:0.72rem; color:#aaa; margin-top:8px;">
    Made with ❤️ on <strong style="color:#0d1b2a;">SAP BTP</strong>
  </div>
</div>"""

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
                cfg = DEFAULT_HANA.copy()
                cfg.update(saved)
                return cfg
        except Exception:
            pass
    return DEFAULT_HANA.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def is_setup_complete():
    """Returns True only if hana_config.json exists and setup_complete is True."""
    if not os.path.exists(CONFIG_FILE):
        return False
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        return cfg.get('setup_complete', False) is True
    except Exception:
        return False

# ── User stats ────────────────────────────────────────────────────────────────
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

def track_login(user_id):
    stats = load_stats()
    if user_id not in stats:
        stats[user_id] = {
            'first_login': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'last_login': None,
            'login_count': 0
        }
    stats[user_id]['last_login'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    stats[user_id]['login_count'] = stats[user_id].get('login_count', 0) + 1
    save_stats(stats)

# ── Email ─────────────────────────────────────────────────────────────────────
def _get_smtp_creds():
    cfg = load_config()
    return cfg.get('sender_email', ''), cfg.get('sender_password', '')

def send_mail(recipient, subject, body):
    sender, password = _get_smtp_creds()
    cfg = load_config()
    app_url = cfg.get('app_url', 'http://localhost:8080')
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        # Plain text fallback
        msg.attach(MIMEText(body, 'plain'))
        # HTML version with footer
        html_body = f"""
<div style="font-family:Arial,sans-serif; max-width:520px; margin:0 auto; padding:24px; background:#f8f9fb; border-radius:12px;">
  <div style="background:linear-gradient(135deg,#0d1b2a,#1a3a5c); padding:16px 20px; border-radius:8px 8px 0 0; margin-bottom:20px;">
    <span style="font-size:1.1rem; font-weight:800; color:white;">🤝 Cust<span style="color:#008fd3;">Track</span></span>
  </div>
  <div style="background:white; padding:20px 24px; border-radius:0 0 8px 8px; border:1px solid #e0e4ea;">
    <pre style="font-family:Arial,sans-serif; white-space:pre-wrap; font-size:0.9rem; color:#1a2332; line-height:1.6;">{body}</pre>
    {_email_footer(app_url)}
  </div>
</div>"""
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.ehlo()
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ Mail sent to {recipient}: {subject}")
        return True
    except Exception as e:
        print(f"❌ Mail error to {recipient}: {e}")
        return False

def send_mail_with_image(recipient, subject, body_html, img_bytes=None, img_name='screenshot.png'):
    sender, password = _get_smtp_creds()
    cfg = load_config()
    app_url = cfg.get('app_url', 'http://localhost:8080')
    try:
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        alt = MIMEMultipart('alternative')
        msg.attach(alt)
        full_html = f"""
<div style="font-family:Arial,sans-serif; max-width:560px; margin:0 auto; padding:24px; background:#f8f9fb; border-radius:12px;">
  <div style="background:linear-gradient(135deg,#0d1b2a,#1a3a5c); padding:16px 20px; border-radius:8px 8px 0 0; margin-bottom:20px;">
    <span style="font-size:1.1rem; font-weight:800; color:white;">🤝 Cust<span style="color:#008fd3;">Track</span></span>
  </div>
  <div style="background:white; padding:20px 24px; border-radius:0 0 8px 8px; border:1px solid #e0e4ea;">
    {body_html}
    {_email_footer(app_url)}
  </div>
</div>"""
        alt.attach(MIMEText(full_html, 'html'))
        if img_bytes:
            img = MIMEImage(img_bytes, name=img_name)
            img.add_header('Content-Disposition', 'attachment', filename=img_name)
            msg.attach(img)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.ehlo()
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        print(f"✅ Mail+image sent to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Mail error to {recipient}: {e}")
        return False

# ── OTP store ─────────────────────────────────────────────────────────────────
_otp_store = {}  # {email: {'otp': '123456', 'expires': timestamp}}

def generate_otp(email):
    otp = str(random.randint(100000, 999999))
    _otp_store[email] = {'otp': otp, 'expires': time.time() + 300}
    return otp

def verify_otp(email, otp):
    entry = _otp_store.get(email)
    if entry and time.time() < entry['expires'] and entry['otp'] == str(otp):
        del _otp_store[email]
        return True
    return False

# ── Persistent HANA connection ────────────────────────────────────────────────
_conn = None
_conn_lock = threading.Lock()

def _make_conn(cfg):
    conn = dbapi.connect(
        address=cfg['host'], port=cfg['port'],
        user=cfg['user'], password=cfg['password'],
        encrypt=True, sslValidateCertificate=False,
        connectTimeout=5000      # 5-second timeout — fail fast
    )
    conn.cursor().execute("SET SCHEMA DBADMIN")
    return conn

def get_db_conn():
    global _conn
    cfg = load_config()
    with _conn_lock:
        if _conn is not None:
            try:
                _conn.cursor().execute("SELECT 1 FROM DUMMY")
                return _conn
            except Exception:
                try: _conn.close()
                except Exception: pass
                _conn = None
        try:
            _conn = _make_conn(cfg)
            return _conn
        except Exception as e:
            print(f"❌ DB ERROR: {e}")
            return None

def invalidate_conn():
    global _conn
    with _conn_lock:
        if _conn:
            try: _conn.close()
            except Exception: pass
        _conn = None

# ── Background jobs ───────────────────────────────────────────────────────────
def check_reminders():
    cfg = load_config()
    try:
        conn = _make_conn(cfg)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, NAME, REMINDER_EMAIL, REMINDER_TIME FROM CUSTOMERS
            WHERE REMINDER_TIME <= ADD_SECONDS(CURRENT_TIMESTAMP, 19800)
            AND REMINDER_SENT = 'N' AND STATUS = 'ACTIVE'
        """)
        for task in cursor.fetchall():
            if send_mail(task[2], f"⏰ Reminder: {task[1]}", f"CustTrack Alert for {task[1]} at {task[3]}"):
                cursor.execute("UPDATE CUSTOMERS SET REMINDER_SENT = 'Y' WHERE ID = ?", (task[0],))
                conn.commit()
        conn.close()
    except Exception:
        pass

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(check_reminders, 'interval', seconds=60)
scheduler.start()

def _warmup():
    try:
        get_db_conn()
        print("✅ HANA connection pre-warmed")
    except Exception:
        pass

threading.Thread(target=_warmup, daemon=True).start()

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_admin():
    return session.get('is_admin') is True

def can_access_settings():
    """True for super admin OR any user listed in settings_users config."""
    if is_admin():
        return True
    cfg = load_config()
    settings_users = [u.strip().lower() for u in cfg.get('settings_users', [])]
    return session.get('user', '').lower() in settings_users

# ── Setup wizard ──────────────────────────────────────────────────────────────
@app.before_request
def check_setup():
    """Redirect every request to /setup until first-run setup is complete."""
    allowed = ('/setup', '/static')
    if not is_setup_complete():
        if not request.path.startswith('/setup') and not request.path.startswith('/static'):
            return redirect('/setup')

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    # If already set up, redirect to login
    if is_setup_complete():
        return redirect('/')

    error = None
    if request.method == 'POST':
        f = request.form
        host         = f.get('host', '').strip()
        port         = int(f.get('port', 443) or 443)
        db_user      = f.get('db_user', 'DBADMIN').strip()
        db_password  = f.get('db_password', '').strip()
        admin_email  = f.get('admin_email', '').strip().lower()
        admin_pw     = f.get('admin_password', '').strip()
        sub_admin    = f.get('sub_admin', '').strip().lower()
        sender_email = f.get('sender_email', '').strip().lower()
        sender_pw    = f.get('sender_password', '').strip()
        app_url      = f.get('app_url', 'http://localhost:8080').strip().rstrip('/')

        # Validate required fields
        if not all([host, db_password, admin_email, admin_pw]):
            error = 'HANA host, HANA password, admin email and admin password are required.'
            return render_template('setup.html', error=error, form=f)

        # Test HANA connection
        try:
            test = dbapi.connect(
                address=host, port=port, user=db_user, password=db_password,
                encrypt=True, sslValidateCertificate=False, connectTimeout=8000
            )
            test.close()
        except Exception as e:
            error = f'HANA connection failed: {str(e)[:200]}. Check host/port/password and try again.'
            return render_template('setup.html', error=error, form=f)

        # Build settings_users list
        settings_users = [u.strip().lower() for u in sub_admin.split(',') if u.strip()]

        new_cfg = {
            'host': host,
            'port': port,
            'user': db_user,
            'password': db_password,
            'admin_email': admin_email,
            'support_email': admin_email,
            'sender_email': sender_email or admin_email,
            'sender_password': sender_pw,
            'admin_password': admin_pw,
            'settings_users': settings_users,
            'app_url': app_url,
            'setup_complete': True
        }
        save_config(new_cfg)
        invalidate_conn()
        return redirect('/')

    return render_template('setup.html', error=error, form={})

@app.route('/setup/test_conn', methods=['POST'])
def setup_test_conn():
    """AJAX endpoint — test HANA connection without saving."""
    data = request.get_json()
    try:
        test = dbapi.connect(
            address=data['host'], port=int(data.get('port', 443)),
            user=data.get('user', 'DBADMIN'), password=data['password'],
            encrypt=True, sslValidateCertificate=False, connectTimeout=8000
        )
        test.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)[:200]})

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['POST'])
def login():
    user_id = request.form.get('user_id', '').strip()
    admin_pw = request.form.get('admin_pw', '').strip()
    if not user_id:
        return redirect('/')
    cfg = load_config()
    admin_email = cfg.get('admin_email', '').strip().lower()
    stored_admin_pw = cfg.get('admin_password', '').strip()

    # Super admin path
    if user_id.lower() == admin_email:
        # Fallback: password provided — check it directly
        if admin_pw and stored_admin_pw and admin_pw == stored_admin_pw:
            session['user'] = admin_email
            session['is_admin'] = True
            session.permanent = True
            track_login(admin_email)
            return redirect(url_for('admin_panel'))
        # Primary: send OTP
        otp = generate_otp(admin_email)
        sent = send_mail(admin_email, 'CustTrack Admin OTP',
                         f'Your CustTrack admin OTP is: {otp}\n\nValid for 5 minutes.\n\nIf you did not request this, ignore this email.')
        if sent:
            session['pending_admin'] = admin_email
            return redirect(url_for('admin_otp'))
        else:
            # OTP failed — offer password fallback on login page
            return render_template('login.html',
                                   error='OTP email could not be sent. Enter your admin password below as a fallback.',
                                   show_admin_pw=True,
                                   admin_email_val=user_id)
    # Regular user
    session['user'] = user_id
    session.permanent = True
    track_login(user_id)
    return redirect(url_for('index'))

@app.route('/admin/otp', methods=['GET', 'POST'])
def admin_otp():
    if 'pending_admin' not in session:
        return redirect('/')
    error = None
    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        email = session['pending_admin']
        if verify_otp(email, otp):
            session.pop('pending_admin', None)
            session['user'] = email
            session['is_admin'] = True
            session.permanent = True
            track_login(email)
            return redirect(url_for('admin_panel'))
        else:
            error = 'Invalid or expired OTP. Please try again.'
    return render_template('admin_otp.html', email=session['pending_admin'], error=error)

@app.route('/admin/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get('pending_admin')
    if not email:
        return jsonify({'success': False})
    otp = generate_otp(email)
    ok = send_mail(email, 'CustTrack Admin OTP', f'Your new admin OTP is: {otp}\n\nValid for 5 minutes.')
    return jsonify({'success': ok})

@app.route('/admin')
def admin_panel():
    if not is_admin():
        return redirect('/')
    stats = load_stats()
    conn = get_db_conn()
    user_data = []
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT CREATED_BY, COUNT(*) FROM CUSTOMERS WHERE STATUS='ACTIVE' GROUP BY CREATED_BY")
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT CREATED_BY, COUNT(*) FROM CUSTOMERS GROUP BY CREATED_BY")
        total_counts = {row[0]: row[1] for row in cursor.fetchall()}
    else:
        counts = {}
        total_counts = {}
    all_users = set(list(stats.keys()) + list(total_counts.keys()))
    for uid in sorted(all_users):
        s = stats.get(uid, {})
        user_data.append({
            'id': uid,
            'first_login': s.get('first_login', '—'),
            'last_login': s.get('last_login', '—'),
            'login_count': s.get('login_count', 0),
            'active_customers': counts.get(uid, 0),
            'total_customers': total_counts.get(uid, 0)
        })
    return render_template('admin.html', users=user_data, user=session['user'])

@app.route('/admin/view/<path:user_id>')
def admin_view_user(user_id):
    if not is_admin():
        return redirect('/')
    conn = get_db_conn()
    customers = []
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ID, NAME, CRM_ID, LOCATION, BTP_INTEREST, COMMENTS,
                   REMINDER_TIME, REMINDER_EMAIL, STATUS
            FROM CUSTOMERS WHERE CREATED_BY = ? ORDER BY ID DESC
        """, (user_id,))
        customers = cursor.fetchall()
    return render_template('index.html', customers=customers, user=session['user'],
                           viewing_user=user_id, is_admin=True, can_settings=True)

@app.route('/admin/delete_user/<path:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    if not is_admin():
        return jsonify({'success': False}), 403
    conn = get_db_conn()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM CUSTOMERS WHERE CREATED_BY = ?", (user_id,))
        conn.commit()
    stats = load_stats()
    stats.pop(user_id, None)
    save_stats(stats)
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    if 'user' not in session:
        return render_template('login.html')
    db_err_flag = request.args.get('db_err') == '1'
    conn = get_db_conn()
    if not conn:
        return render_template('index.html', customers=[], user=session['user'],
                               is_admin=is_admin(), db_error=True, can_settings=can_access_settings())
    if db_err_flag:
        # DB recovered — show banner once then continue normally
        pass
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ID, NAME, CRM_ID, LOCATION, BTP_INTEREST, COMMENTS,
               REMINDER_TIME, REMINDER_EMAIL, STATUS
        FROM CUSTOMERS WHERE CREATED_BY = ? ORDER BY ID DESC
    """, (session['user'],))
    data = cursor.fetchall()
    return render_template('index.html', customers=data, user=session['user'],
                           is_admin=is_admin(), can_settings=can_access_settings())

@app.route('/add', methods=['POST'])
def add():
    if 'user' not in session:
        return redirect('/')
    f = request.form
    r_time = f.get('rem_time').replace('T', ' ') if f.get('rem_time') else None
    conn = get_db_conn()
    if not conn:
        return redirect('/?db_err=1')
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO CUSTOMERS (NAME, CRM_ID, LOCATION, BTP_INTEREST, COMMENTS, "
            "REMINDER_TIME, REMINDER_EMAIL, REMINDER_SENT, STATUS, CREATED_BY) "
            "VALUES (?,?,?,?,?,?,?,'N','ACTIVE',?)",
            (f.get('name'), f.get('crm_id'), f.get('location'),
             f.get('interest'), f.get('comments'), r_time,
             f.get('rem_email'), session['user'])
        )
        conn.commit()
    except Exception as e:
        print(f"❌ Add error: {e}")
        invalidate_conn()
        return redirect('/?db_err=1')
    return redirect('/')

@app.route('/edit', methods=['POST'])
def edit():
    if 'user' not in session:
        return redirect('/')
    f = request.form
    r_time = f.get('rem_time').replace('T', ' ') if f.get('rem_time') else None
    conn = get_db_conn()
    if not conn:
        return redirect('/?db_err=1')
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE CUSTOMERS SET NAME=?, CRM_ID=?, LOCATION=?, BTP_INTEREST=?, "
            "COMMENTS=?, REMINDER_TIME=?, REMINDER_EMAIL=?, REMINDER_SENT='N' "
            "WHERE ID=? AND CREATED_BY=?",
            (f.get('name'), f.get('crm_id'), f.get('location'),
             f.get('interest'), f.get('comments'), r_time,
             f.get('rem_email'), f.get('id'), session['user'])
        )
        conn.commit()
    except Exception as e:
        print(f"❌ Edit error: {e}")
        invalidate_conn()
        return redirect('/?db_err=1')
    return redirect('/')

@app.route('/archive/<int:id>', methods=['POST'])
def archive(id):
    if 'user' not in session:
        return jsonify({"success": False}), 401
    conn = get_db_conn()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE CUSTOMERS SET STATUS = 'ARCHIVED' WHERE ID = ? AND CREATED_BY = ?",
                       (id, session['user']))
        conn.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/restore/<int:id>', methods=['POST'])
def restore(id):
    if 'user' not in session:
        return jsonify({"success": False}), 401
    conn = get_db_conn()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE CUSTOMERS SET STATUS = 'ACTIVE' WHERE ID = ? AND CREATED_BY = ?",
                       (id, session['user']))
        conn.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 500

@app.route('/export')
def export():
    if 'user' not in session:
        return redirect('/')
    conn = get_db_conn()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT NAME, CRM_ID, LOCATION, BTP_INTEREST, STATUS FROM CUSTOMERS WHERE CREATED_BY = ?",
                       (session['user'],))
        df = pd.DataFrame(cursor.fetchall(),
                          columns=['Customer', 'CRM', 'Location', 'Interest', 'Status'])
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        out.seek(0)
        return send_file(out,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name='CustTrack_Export.xlsx')
    return "Export Failed"

@app.route('/help', methods=['POST'])
def help_request():
    if 'user' not in session:
        return jsonify({'success': False}), 401
    cfg = load_config()
    support_email = cfg.get('support_email', cfg.get('sender_email', cfg.get('admin_email', '')))
    data = request.get_json()
    message = data.get('message', '').strip()
    screenshot_b64 = data.get('screenshot', '')
    user = session['user']
    subject = f'CustTrack Help Request from {user}'
    body_html = f"""
    <h2>Help Request — CustTrack</h2>
    <p><strong>From:</strong> {user}</p>
    <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <p><strong>Message:</strong><br>{message or '(no message)'}</p>
    {'<p><strong>Screenshot attached.</strong></p>' if screenshot_b64 else ''}
    """
    img_bytes = None
    if screenshot_b64:
        try:
            header, encoded = screenshot_b64.split(',', 1)
            img_bytes = base64.b64decode(encoded)
        except Exception:
            img_bytes = None
    ok = send_mail_with_image(support_email, subject, body_html, img_bytes)
    return jsonify({'success': ok})

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user' not in session:
        return redirect('/')
    if not can_access_settings():
        return redirect('/')
    cfg = load_config()
    msg = None
    msg_type = 'success'
    db_error = session.pop('db_error', False)
    if db_error:
        msg = '❌ Database connection failed. Update the settings below and click Save & Test.'
        msg_type = 'error'
    db_ok = None

    if request.method == 'POST':
        submitted_pw = request.form.get('password', '').strip()
        new_sender_pw = request.form.get('sender_password', '').strip()
        new_admin_pw = request.form.get('admin_password', '').strip()
        new_cfg = {
            'host': request.form.get('host', '').strip(),
            'port': int(request.form.get('port', 443)),
            'user': request.form.get('user', '').strip(),
            'password': submitted_pw if submitted_pw else cfg['password'],
            'admin_email': request.form.get('admin_email', '').strip().lower(),
            'support_email': request.form.get('support_email', '').strip().lower(),
            'sender_email': request.form.get('sender_email', '').strip().lower(),
            'sender_password': new_sender_pw if new_sender_pw else cfg.get('sender_password', ''),
            'admin_password': new_admin_pw if new_admin_pw else cfg.get('admin_password', ''),
            'settings_users': [u.strip() for u in request.form.get('settings_users', '').split(',') if u.strip()],
            'setup_complete': True
        }
        save_config(new_cfg)
        cfg = new_cfg
        invalidate_conn()
        try:
            test_conn = _make_conn(new_cfg)
            test_conn.close()
            msg = '✅ Settings saved and connection successful.'
            msg_type = 'success'
            db_ok = True
        except Exception as e:
            msg = f'⚠️ Settings saved, but connection test failed: {str(e)[:200]}'
            msg_type = 'error'
            db_ok = False

    if os.path.exists(CONFIG_FILE):
        pw_source = 'hana_config.json'
    elif os.environ.get('HANA_PASSWORD'):
        pw_source = 'Environment variable HANA_PASSWORD'
    else:
        pw_source = 'Default (hardcoded)'

    class Cfg:
        pass
    c = Cfg()
    c.host            = cfg['host']
    c.port            = cfg['port']
    c.user            = cfg['user']
    c.password        = cfg['password']
    c.admin_email     = cfg.get('admin_email', '')
    c.support_email   = cfg.get('support_email', '')
    c.sender_email    = cfg.get('sender_email', '')
    c.sender_password = cfg.get('sender_password', '')
    c.admin_password  = cfg.get('admin_password', '')

    settings_users_str = ', '.join(cfg.get('settings_users', []))
    return render_template('settings.html',
                           cfg=c, db_ok=db_ok,
                           pw_len=len(cfg.get('password', '')),
                           pw_source=pw_source,
                           msg=msg, msg_type=msg_type,
                           user=session['user'],
                           is_admin=is_admin(),
                           settings_users_str=settings_users_str)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))