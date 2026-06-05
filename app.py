from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import init_db, get_db
from datetime import datetime, date
import hashlib
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sgrdms_tropical_secret_2026')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Accès non autorisé.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ─── AUTH ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_val = request.form['login']
        password = hash_password(request.form['password'])
        db = get_db()
        user = db.execute('SELECT * FROM Utilisateur WHERE login=? AND mot_de_passe=?',
                          (login_val, password)).fetchone()
        if user:
            session['user_id'] = user['id_utilisateur']
            session['login'] = user['login']
            session['role'] = user['role']
            flash(f'Bienvenue {user["login"]} !', 'success')
            return redirect(url_for('dashboard'))
        flash('Identifiants incorrects.', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Déconnexion réussie.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    routes = {
        'admin': 'admin_dashboard',
        'medecin': 'medecin_dashboard',
        'pharmacien': 'pharmacien_dashboard',
        'patient': 'patient_dashboard',
        'assureur': 'assureur_dashboard',
        'accueil': 'accueil_dashboard',
        'secretaire': 'accueil_dashboard',
    }
    return redirect(url_for(routes.get(role, 'login')))

# ─── ADMIN ────────────────────────────────────────────────────────────────────
@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    db = get_db()
    stats = {
        'patients': db.execute('SELECT COUNT(*) as c FROM Patient').fetchone()['c'],
        'medecins': db.execute('SELECT COUNT(*) as c FROM Medecin').fetchone()['c'],
        'rdv_today': db.execute("SELECT COUNT(*) as c FROM Rendez_vous WHERE date(date_rdv_prevue)=date('now')").fetchone()['c'],
        'factures_impayees': db.execute("SELECT COUNT(*) as c FROM Facture WHERE statut='en attente'").fetchone()['c'],
        'utilisateurs': db.execute('SELECT COUNT(*) as c FROM Utilisateur').fetchone()['c'],
        'centres': db.execute('SELECT COUNT(*) as c FROM Centre_Medical').fetchone()['c'],
        'consultations': db.execute('SELECT COUNT(*) as c FROM Consultation').fetchone()['c'],
        'ordonnances': db.execute('SELECT COUNT(*) as c FROM Ordonnance').fetchone()['c'],
    }
    rdvs_today = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient, m.nom_medecin
                               FROM Rendez_vous r
                               JOIN Patient p ON r.id_patient=p.id_patient
                               JOIN Medecin m ON r.id_medecin=m.id_medecin
                               WHERE date(r.date_rdv_prevue)=date('now')
                               ORDER BY r.heure LIMIT 10''').fetchall()
    return render_template('admin/dashboard.html', stats=stats, rdvs_today=rdvs_today)

@app.route('/admin/utilisateurs')
@role_required('admin')
def admin_utilisateurs():
    db = get_db()
    users = db.execute('SELECT * FROM Utilisateur ORDER BY id_utilisateur DESC').fetchall()
    return render_template('admin/utilisateurs.html', users=users)

@app.route('/admin/utilisateurs/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_utilisateur():
    if request.method == 'POST':
        db = get_db()
        try:
            db.execute('INSERT INTO Utilisateur (login, mot_de_passe, role) VALUES (?,?,?)',
                       (request.form['login'], hash_password(request.form['mot_de_passe']), request.form['role']))
            db.commit()
            flash('Utilisateur créé.', 'success')
            return redirect(url_for('admin_utilisateurs'))
        except Exception as e:
            flash(f'Erreur : {e}', 'danger')
    return render_template('admin/ajouter_utilisateur.html')

@app.route('/admin/utilisateurs/supprimer/<int:id>')
@role_required('admin')
def admin_supprimer_utilisateur(id):
    db = get_db()
    db.execute('DELETE FROM Utilisateur WHERE id_utilisateur=?', (id,))
    db.commit()
    flash('Utilisateur supprimé.', 'warning')
    return redirect(url_for('admin_utilisateurs'))

@app.route('/admin/patients')
@role_required('admin')
def admin_patients():
    db = get_db()
    patients = db.execute('''SELECT p.*, u.login FROM Patient p
                             LEFT JOIN Utilisateur u ON p.id_utilisateur=u.id_utilisateur
                             ORDER BY p.id_patient DESC''').fetchall()
    return render_template('admin/patients.html', patients=patients)

@app.route('/admin/patients/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_patient():
    db = get_db()
    if request.method == 'POST':
        try:
            cur = db.execute('INSERT INTO Utilisateur (login, mot_de_passe, role) VALUES (?,?,?)',
                             (request.form['login'], hash_password(request.form['mot_de_passe']), 'patient'))
            id_u = cur.lastrowid
            db.execute('''INSERT INTO Patient (nom_patient, prenom_patient, date_naissance, sexe,
                          telephone, adresse, mail, id_utilisateur)
                          VALUES (?,?,?,?,?,?,?,?)''',
                       (request.form['nom'], request.form['prenom'], request.form['date_naissance'],
                        request.form['sexe'], request.form['telephone'], request.form['adresse'],
                        request.form['mail'], id_u))
            id_p = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('''INSERT INTO Dossier_Medical (date_creation, antecedents, allergies,
                          groupe_sanguin, notes, id_patient)
                          VALUES (date('now'),?,?,?,?,?)''',
                       (request.form.get('antecedents',''), request.form.get('allergies',''),
                        request.form.get('groupe_sanguin',''), '', id_p))
            db.commit()
            flash('Patient enregistré avec succès.', 'success')
            return redirect(url_for('admin_patients'))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('admin/ajouter_patient.html')

@app.route('/admin/medecins')
@role_required('admin')
def admin_medecins():
    db = get_db()
    medecins = db.execute('''SELECT m.*, u.login FROM Medecin m
                             LEFT JOIN Utilisateur u ON m.id_utilisateur=u.id_utilisateur
                             ORDER BY m.id_medecin DESC''').fetchall()
    return render_template('admin/medecins.html', medecins=medecins)

@app.route('/admin/medecins/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_medecin():
    db = get_db()
    if request.method == 'POST':
        try:
            cur = db.execute('INSERT INTO Utilisateur (login, mot_de_passe, role) VALUES (?,?,?)',
                             (request.form['login'], hash_password(request.form['mot_de_passe']), 'medecin'))
            id_u = cur.lastrowid
            db.execute('''INSERT INTO Medecin (nom_medecin, prenom_medecin, telephone, email,
                          specialite, actif_teleconsult, disponibilite, id_utilisateur)
                          VALUES (?,?,?,?,?,?,?,?)''',
                       (request.form['nom'], request.form['prenom'], request.form['telephone'],
                        request.form['email'], request.form['specialite'],
                        1 if request.form.get('actif_teleconsult') else 0,
                        request.form.get('disponibilite',''), id_u))
            db.commit()
            flash('Médecin ajouté.', 'success')
            return redirect(url_for('admin_medecins'))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('admin/ajouter_medecin.html')

@app.route('/admin/centres')
@role_required('admin')
def admin_centres():
    db = get_db()
    centres = db.execute('SELECT * FROM Centre_Medical ORDER BY id_centre DESC').fetchall()
    return render_template('admin/centres.html', centres=centres)

@app.route('/admin/centres/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_centre():
    db = get_db()
    if request.method == 'POST':
        db.execute('INSERT INTO Centre_Medical (nom_centre, adresse_centre, type_centre, telephone, ville) VALUES (?,?,?,?,?)',
                   (request.form['nom_centre'], request.form['adresse'], request.form['type_centre'],
                    request.form['telephone'], request.form['ville']))
        db.commit()
        flash('Centre ajouté.', 'success')
        return redirect(url_for('admin_centres'))
    return render_template('admin/ajouter_centre.html')

@app.route('/admin/services')
@role_required('admin')
def admin_services():
    db = get_db()
    services = db.execute('''SELECT s.*, c.nom_centre FROM Service_Medical s
                             JOIN Centre_Medical c ON s.id_centre=c.id_centre
                             ORDER BY s.id_service DESC''').fetchall()
    centres = db.execute('SELECT * FROM Centre_Medical').fetchall()
    return render_template('admin/services.html', services=services, centres=centres)

@app.route('/admin/services/ajouter', methods=['POST'])
@role_required('admin')
def admin_ajouter_service():
    db = get_db()
    db.execute('INSERT INTO Service_Medical (nom_service, id_centre) VALUES (?,?)',
               (request.form['nom_service'], request.form['id_centre']))
    db.commit()
    flash('Service ajouté.', 'success')
    return redirect(url_for('admin_services'))

@app.route('/admin/assurances')
@role_required('admin')
def admin_assurances():
    db = get_db()
    assurances = db.execute('SELECT * FROM Assurance ORDER BY id_assurance DESC').fetchall()
    return render_template('admin/assurances.html', assurances=assurances)

@app.route('/admin/assurances/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_assurance():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO Assurance (nom_compagnie, numero_contrat, taux_prise_charge,
                      type_assurance, date_debut, fin_couverture, statut, plafond_annuel,
                      statut_tiers_pay, type_prise_charge) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                   (request.form['nom_compagnie'], request.form['numero_contrat'],
                    float(request.form['taux']), request.form['type_assurance'],
                    request.form['date_debut'], request.form['fin_couverture'],
                    request.form['statut'], float(request.form.get('plafond', 0)),
                    1 if request.form.get('tiers_pay') else 0,
                    request.form.get('type_prise_charge', '')))
        db.commit()
        flash('Assurance ajoutée.', 'success')
        return redirect(url_for('admin_assurances'))
    return render_template('admin/ajouter_assurance.html')

@app.route('/admin/rendez-vous')
@role_required('admin')
def admin_rendez_vous():
    db = get_db()
    rdvs = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient,
                         m.nom_medecin, m.prenom_medecin, s.nom_service
                         FROM Rendez_vous r
                         JOIN Patient p ON r.id_patient=p.id_patient
                         JOIN Medecin m ON r.id_medecin=m.id_medecin
                         JOIN Service_Medical s ON r.id_service=s.id_service
                         ORDER BY r.date_rdv_prevue DESC''').fetchall()
    return render_template('admin/rendez_vous.html', rdvs=rdvs)

@app.route('/admin/rendez-vous/ajouter', methods=['GET', 'POST'])
@role_required('admin')
def admin_ajouter_rdv():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO Rendez_vous (date_rdv_prevue, heure, type_rdv, statut_rdv,
                      motif, id_patient, id_medecin, id_service)
                      VALUES (?,?,?,?,?,?,?,?)''',
                   (request.form['date_rdv'], request.form['heure'], request.form['type_rdv'],
                    'planifié', request.form['motif'], request.form['id_patient'],
                    request.form['id_medecin'], request.form['id_service']))
        db.commit()
        flash('Rendez-vous planifié.', 'success')
        return redirect(url_for('admin_rendez_vous'))
    patients = db.execute('SELECT id_patient, nom_patient, prenom_patient FROM Patient').fetchall()
    medecins = db.execute('SELECT id_medecin, nom_medecin, prenom_medecin, specialite FROM Medecin').fetchall()
    services = db.execute('''SELECT s.id_service, s.nom_service, c.nom_centre
                             FROM Service_Medical s JOIN Centre_Medical c ON s.id_centre=c.id_centre''').fetchall()
    return render_template('admin/ajouter_rdv.html', patients=patients, medecins=medecins, services=services)

@app.route('/admin/historique')
@role_required('admin')
def admin_historique():
    db = get_db()
    historique = db.execute('''SELECT h.*, u.login FROM Historique h
                               LEFT JOIN Utilisateur u ON h.id_utilisateur=u.id_utilisateur
                               ORDER BY h.date_action DESC LIMIT 200''').fetchall()
    return render_template('admin/historique.html', historique=historique)

@app.route('/admin/urgences')
@role_required('admin')
def admin_urgences():
    db = get_db()
    urgences = db.execute('''SELECT u.*, p.nom_patient, p.prenom_patient, p.telephone
                             FROM Urgence u JOIN Patient p ON u.id_patient=p.id_patient
                             ORDER BY u.date_arrivee DESC''').fetchall()
    patients = db.execute('SELECT id_patient, nom_patient, prenom_patient FROM Patient').fetchall()
    services = db.execute('''SELECT s.id_service, s.nom_service FROM Service_Medical s''').fetchall()
    return render_template('admin/urgences.html', urgences=urgences, patients=patients, services=services)

@app.route('/admin/urgences/ajouter', methods=['POST'])
@role_required('admin')
def admin_ajouter_urgence():
    db = get_db()
    db.execute('''INSERT INTO Urgence (date_arrivee, priorite, motif_urgence, statut,
                  id_patient, id_service) VALUES (datetime('now'),?,?,?,?,?)''',
               (request.form['priorite'], request.form['motif'],
                'en attente', request.form['id_patient'], request.form['id_service']))
    db.commit()
    flash('Urgence enregistrée.', 'success')
    return redirect(url_for('admin_urgences'))

@app.route('/admin/liste-attente')
@role_required('admin')
def admin_liste_attente():
    db = get_db()
    attente = db.execute('''SELECT l.*, p.nom_patient, p.prenom_patient, c.nom_centre
                            FROM Liste_Attente l
                            JOIN Patient p ON l.id_patient=p.id_patient
                            JOIN Centre_Medical c ON l.id_centre=c.id_centre
                            ORDER BY l.priorite DESC, l.date_inscription''').fetchall()
    return render_template('admin/liste_attente.html', attente=attente)

# ─── ACCUEIL / SECRÉTAIRE ─────────────────────────────────────────────────────
@app.route('/accueil')
@role_required('accueil', 'secretaire')
def accueil_dashboard():
    db = get_db()
    stats = {
        'rdv_today': db.execute("SELECT COUNT(*) as c FROM Rendez_vous WHERE date(date_rdv_prevue)=date('now')").fetchone()['c'],
        'patients_today': db.execute("SELECT COUNT(*) as c FROM Patient WHERE date(rowid)=date('now')").fetchone()['c'],
        'urgences': db.execute("SELECT COUNT(*) as c FROM Urgence WHERE statut='en attente'").fetchone()['c'],
        'attente': db.execute("SELECT COUNT(*) as c FROM Liste_Attente WHERE statut='en attente'").fetchone()['c'],
    }
    rdvs_today = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient, m.nom_medecin, s.nom_service
                               FROM Rendez_vous r
                               JOIN Patient p ON r.id_patient=p.id_patient
                               JOIN Medecin m ON r.id_medecin=m.id_medecin
                               JOIN Service_Medical s ON r.id_service=s.id_service
                               WHERE date(r.date_rdv_prevue)=date('now')
                               ORDER BY r.heure''').fetchall()
    return render_template('accueil/dashboard.html', stats=stats, rdvs_today=rdvs_today)

@app.route('/accueil/patients')
@role_required('accueil', 'secretaire')
def accueil_patients():
    db = get_db()
    patients = db.execute('''SELECT p.*, u.login FROM Patient p
                             LEFT JOIN Utilisateur u ON p.id_utilisateur=u.id_utilisateur
                             ORDER BY p.id_patient DESC''').fetchall()
    return render_template('accueil/patients.html', patients=patients)

@app.route('/accueil/patients/ajouter', methods=['GET', 'POST'])
@role_required('accueil', 'secretaire')
def accueil_ajouter_patient():
    db = get_db()
    if request.method == 'POST':
        try:
            cur = db.execute('INSERT INTO Utilisateur (login, mot_de_passe, role) VALUES (?,?,?)',
                             (request.form['login'], hash_password(request.form['mot_de_passe']), 'patient'))
            id_u = cur.lastrowid
            db.execute('''INSERT INTO Patient (nom_patient, prenom_patient, date_naissance, sexe,
                          telephone, adresse, mail, id_utilisateur) VALUES (?,?,?,?,?,?,?,?)''',
                       (request.form['nom'], request.form['prenom'], request.form['date_naissance'],
                        request.form['sexe'], request.form['telephone'], request.form['adresse'],
                        request.form['mail'], id_u))
            id_p = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            db.execute('''INSERT INTO Dossier_Medical (date_creation, antecedents, allergies,
                          groupe_sanguin, notes, id_patient) VALUES (date('now'),?,?,?,?,?)''',
                       (request.form.get('antecedents',''), request.form.get('allergies',''),
                        request.form.get('groupe_sanguin',''), '', id_p))
            db.commit()
            flash('Patient enregistré avec succès.', 'success')
            return redirect(url_for('accueil_patients'))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('accueil/ajouter_patient.html')

@app.route('/accueil/rendez-vous')
@role_required('accueil', 'secretaire')
def accueil_rendez_vous():
    db = get_db()
    rdvs = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient,
                         m.nom_medecin, s.nom_service, c.nom_centre
                         FROM Rendez_vous r
                         JOIN Patient p ON r.id_patient=p.id_patient
                         JOIN Medecin m ON r.id_medecin=m.id_medecin
                         JOIN Service_Medical s ON r.id_service=s.id_service
                         JOIN Centre_Medical c ON s.id_centre=c.id_centre
                         ORDER BY r.date_rdv_prevue DESC''').fetchall()
    return render_template('accueil/rendez_vous.html', rdvs=rdvs)

@app.route('/accueil/rendez-vous/ajouter', methods=['GET', 'POST'])
@role_required('accueil', 'secretaire')
def accueil_ajouter_rdv():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO Rendez_vous (date_rdv_prevue, heure, type_rdv, statut_rdv,
                      motif, id_patient, id_medecin, id_service) VALUES (?,?,?,?,?,?,?,?)''',
                   (request.form['date_rdv'], request.form['heure'], request.form['type_rdv'],
                    'planifié', request.form['motif'], request.form['id_patient'],
                    request.form['id_medecin'], request.form['id_service']))
        db.commit()
        flash('Rendez-vous planifié.', 'success')
        return redirect(url_for('accueil_rendez_vous'))
    patients = db.execute('SELECT id_patient, nom_patient, prenom_patient FROM Patient').fetchall()
    medecins = db.execute('SELECT id_medecin, nom_medecin, prenom_medecin, specialite FROM Medecin').fetchall()
    services = db.execute('''SELECT s.id_service, s.nom_service, c.nom_centre
                             FROM Service_Medical s JOIN Centre_Medical c ON s.id_centre=c.id_centre''').fetchall()
    return render_template('accueil/ajouter_rdv.html', patients=patients, medecins=medecins, services=services)

@app.route('/accueil/urgences', methods=['GET', 'POST'])
@role_required('accueil', 'secretaire')
def accueil_urgences():
    db = get_db()
    if request.method == 'POST':
        db.execute('''INSERT INTO Urgence (date_arrivee, priorite, motif_urgence, statut,
                      id_patient, id_service) VALUES (datetime('now'),?,?,?,?,?)''',
                   (request.form['priorite'], request.form['motif'],
                    'en attente', request.form['id_patient'], request.form['id_service']))
        db.commit()
        flash('Urgence enregistrée.', 'success')
    urgences = db.execute('''SELECT u.*, p.nom_patient, p.prenom_patient, s.nom_service
                             FROM Urgence u JOIN Patient p ON u.id_patient=p.id_patient
                             JOIN Service_Medical s ON u.id_service=s.id_service
                             ORDER BY u.date_arrivee DESC''').fetchall()
    patients = db.execute('SELECT id_patient, nom_patient, prenom_patient FROM Patient').fetchall()
    services = db.execute('SELECT * FROM Service_Medical').fetchall()
    return render_template('accueil/urgences.html', urgences=urgences, patients=patients, services=services)

@app.route('/accueil/liste-attente')
@role_required('accueil', 'secretaire')
def accueil_liste_attente():
    db = get_db()
    attente = db.execute('''SELECT l.*, p.nom_patient, p.prenom_patient, c.nom_centre
                            FROM Liste_Attente l
                            JOIN Patient p ON l.id_patient=p.id_patient
                            JOIN Centre_Medical c ON l.id_centre=c.id_centre
                            ORDER BY l.priorite DESC, l.date_inscription''').fetchall()
    patients = db.execute('SELECT id_patient, nom_patient, prenom_patient FROM Patient').fetchall()
    centres = db.execute('SELECT * FROM Centre_Medical').fetchall()
    return render_template('accueil/liste_attente.html', attente=attente, patients=patients, centres=centres)

@app.route('/accueil/liste-attente/ajouter', methods=['POST'])
@role_required('accueil', 'secretaire')
def accueil_ajouter_attente():
    db = get_db()
    db.execute('''INSERT INTO Liste_Attente (date_inscription, priorite, statut, id_patient, id_centre)
                  VALUES (datetime('now'),?,?,?,?)''',
               (request.form['priorite'], 'en attente',
                request.form['id_patient'], request.form['id_centre']))
    db.commit()
    flash('Patient ajouté à la liste d\'attente.', 'success')
    return redirect(url_for('accueil_liste_attente'))


@app.route('/accueil/urgences/ajouter', methods=['GET', 'POST'])
@role_required('secretaire')
def accueil_ajouter_urgence():
    db = get_db()
    if request.method == 'POST':
        id_patient = request.form['id_patient']
        niveau = request.form['niveau_triage']
        motif = request.form['motif']
        observations = request.form.get('observations', '')
        id_medecin = request.form.get('id_medecin') or None
        id_service = request.form.get('id_service') or None
        db.execute("""INSERT INTO Urgence (motif, niveau_triage, statut, observations, id_patient, id_service, id_medecin)
                      VALUES (?,?,?,?,?,?,?)""",
                   (motif, niveau, 'en attente', observations, id_patient, id_service, id_medecin))
        db.commit()
        flash('Cas d urgence enregistré.', 'success')
        return redirect(url_for('accueil_urgences'))
    patients = db.execute('SELECT * FROM Patient ORDER BY nom_patient').fetchall()
    medecins = db.execute('SELECT * FROM Medecin').fetchall()
    services = db.execute('SELECT s.*, c.nom_centre FROM Service_Medical s JOIN Centre_Medical c ON s.id_centre=c.id_centre').fetchall()
    return render_template('accueil/ajouter_urgence.html', patients=patients, medecins=medecins, services=services)

@app.route('/accueil/factures')
@role_required('accueil', 'secretaire')
def accueil_factures():
    db = get_db()
    factures = db.execute('''SELECT f.*, p.nom_patient, p.prenom_patient, a.nom_compagnie
                             FROM Facture f JOIN Patient p ON f.id_patient=p.id_patient
                             LEFT JOIN Assurance a ON f.id_assurance=a.id_assurance
                             ORDER BY f.date_facture DESC''').fetchall()
    return render_template('accueil/factures.html', factures=factures)

# ─── MÉDECIN ──────────────────────────────────────────────────────────────────
@app.route('/medecin')
@role_required('medecin')
def medecin_dashboard():
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    if not medecin:
        flash('Profil médecin introuvable.', 'danger')
        return redirect(url_for('login'))
    rdvs_today = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient
                               FROM Rendez_vous r JOIN Patient p ON r.id_patient=p.id_patient
                               WHERE r.id_medecin=? AND date(r.date_rdv_prevue)=date('now')
                               AND r.statut_rdv != 'annulé' ORDER BY r.heure''',
                            (medecin['id_medecin'],)).fetchall()
    stats = {
        'rdv_today': len(rdvs_today),
        'consultations': db.execute('SELECT COUNT(*) as c FROM Consultation WHERE id_medecin=?',
                                    (medecin['id_medecin'],)).fetchone()['c'],
        'ordonnances': db.execute('SELECT COUNT(*) as c FROM Ordonnance WHERE id_medecin=?',
                                  (medecin['id_medecin'],)).fetchone()['c'],
        'teleconsults': db.execute('SELECT COUNT(*) as c FROM Teleconsultation WHERE id_medecin=?',
                                   (medecin['id_medecin'],)).fetchone()['c'],
    }
    return render_template('medecin/dashboard.html', medecin=medecin, rdvs_today=rdvs_today, stats=stats)

@app.route('/medecin/agenda')
@role_required('medecin')
def medecin_agenda():
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    rdvs = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient, s.nom_service,
                         p.id_patient
                         FROM Rendez_vous r JOIN Patient p ON r.id_patient=p.id_patient
                         JOIN Service_Medical s ON r.id_service=s.id_service
                         WHERE r.id_medecin=? ORDER BY r.date_rdv_prevue DESC''',
                      (medecin['id_medecin'],)).fetchall()
    return render_template('medecin/agenda.html', rdvs=rdvs, medecin=medecin)

@app.route('/medecin/consultation/nouvelle/<int:id_rdv>', methods=['GET', 'POST'])
@role_required('medecin')
def medecin_nouvelle_consultation(id_rdv):
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    rdv = db.execute('''SELECT r.*, p.nom_patient, p.prenom_patient, p.id_patient
                        FROM Rendez_vous r JOIN Patient p ON r.id_patient=p.id_patient
                        WHERE r.id_rdv=?''', (id_rdv,)).fetchone()
    dossier = db.execute('SELECT * FROM Dossier_Medical WHERE id_patient=?', (rdv['id_patient'],)).fetchone()
    if request.method == 'POST':
        try:
            cur = db.execute('''INSERT INTO Consultation (statut, observations, heure, diagnostic,
                                constantes_vital, id_medecin, id_rdv, id_dossier)
                                VALUES (?,?,time('now'),?,?,?,?,?)''',
                             ('terminée', request.form['observations'], request.form['diagnostic'],
                              request.form['constantes'], medecin['id_medecin'], id_rdv, dossier['id_dossier']))
            id_c = cur.lastrowid
            db.execute("UPDATE Rendez_vous SET statut_rdv='effectué', date_rdv_reelle=datetime('now') WHERE id_rdv=?",
                       (id_rdv,))
            montant = float(request.form.get('montant_total', 10000))
            db.execute('''INSERT INTO Facture (date_facture, montant_total, montant_patient,
                          montant_assurance, montant_restant, statut, id_patient, id_consultation)
                          VALUES (date('now'),?,?,0,?,'en attente',?,?)''',
                       (montant, montant, montant, rdv['id_patient'], id_c))
            db.execute('''INSERT INTO Historique (date_action, type_action, description, action,
                          id_utilisateur, id_consultation)
                          VALUES (datetime('now'),'création','Consultation créée','Consultation',?,?)''',
                       (session['user_id'], id_c))
            db.commit()
            flash('Consultation enregistrée.', 'success')
            return redirect(url_for('medecin_consultation_detail', id_consult=id_c))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('medecin/nouvelle_consultation.html', rdv=rdv, dossier=dossier, medecin=medecin)

@app.route('/medecin/consultation/<int:id_consult>')
@role_required('medecin')
def medecin_consultation_detail(id_consult):
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    consult = db.execute('''SELECT c.*, p.nom_patient, p.prenom_patient, r.motif
                            FROM Consultation c
                            JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                            JOIN Patient p ON r.id_patient=p.id_patient
                            WHERE c.id_consultation=?''', (id_consult,)).fetchone()
    ordonnances = db.execute('''SELECT o.*, COUNT(lo.id_ligne) as nb_medic FROM Ordonnance o
                                LEFT JOIN Ligne_Ordonnance lo ON o.id_ordonnance=lo.id_ordonnance
                                WHERE o.id_consultation=? GROUP BY o.id_ordonnance''',
                             (id_consult,)).fetchall()
    return render_template('medecin/consultation_detail.html', consult=consult,
                           ordonnances=ordonnances, medecin=medecin)

@app.route('/medecin/ordonnance/nouvelle/<int:id_consult>', methods=['GET', 'POST'])
@role_required('medecin')
def medecin_nouvelle_ordonnance(id_consult):
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    consult = db.execute('''SELECT c.*, p.nom_patient, p.prenom_patient FROM Consultation c
                            JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                            JOIN Patient p ON r.id_patient=p.id_patient
                            WHERE c.id_consultation=?''', (id_consult,)).fetchone()
    medicaments = db.execute('SELECT * FROM Medicament ORDER BY nom_medicament').fetchall()
    if request.method == 'POST':
        try:
            cur = db.execute('''INSERT INTO Ordonnance (date_ordonnance, validite, instructions,
                                id_medecin, id_consultation) VALUES (date('now'),?,?,?,?)''',
                             (request.form['validite'], request.form['instructions'],
                              medecin['id_medecin'], id_consult))
            id_o = cur.lastrowid
            ids = request.form.getlist('id_medicament[]')
            pos = request.form.getlist('posologie[]')
            dur = request.form.getlist('duree[]')
            qte = request.form.getlist('quantite[]')
            for i in range(len(ids)):
                if ids[i]:
                    db.execute('''INSERT INTO Ligne_Ordonnance (posologie, duree_traitement,
                                  quantite, nombre_medic, id_ordonnance, id_medicament)
                                  VALUES (?,?,?,1,?,?)''',
                               (pos[i], int(dur[i]), int(qte[i]), id_o, int(ids[i])))
            db.commit()
            flash('Ordonnance créée.', 'success')
            return redirect(url_for('medecin_consultation_detail', id_consult=id_consult))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('medecin/nouvelle_ordonnance.html', consult=consult, medicaments=medicaments)

@app.route('/medecin/teleconsultations')
@role_required('medecin')
def medecin_teleconsultations():
    db = get_db()
    medecin = db.execute('SELECT * FROM Medecin WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    teleconsults = db.execute('''SELECT t.*, p.nom_patient, p.prenom_patient
                                 FROM Teleconsultation t
                                 JOIN Consultation c ON t.id_consultation=c.id_consultation
                                 JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                 JOIN Patient p ON r.id_patient=p.id_patient
                                 WHERE t.id_medecin=? ORDER BY t.heure DESC''',
                              (medecin['id_medecin'],)).fetchall()
    return render_template('medecin/teleconsultations.html', teleconsults=teleconsults, medecin=medecin)

@app.route('/medecin/dossier/<int:id_patient>')
@role_required('medecin')
def medecin_dossier_patient(id_patient):
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_patient=?', (id_patient,)).fetchone()
    dossier = db.execute('SELECT * FROM Dossier_Medical WHERE id_patient=?', (id_patient,)).fetchone()
    consultations = db.execute('''SELECT c.*, r.date_rdv_prevue, r.motif, m.nom_medecin, m.prenom_medecin
                                  FROM Consultation c JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                  JOIN Medecin m ON c.id_medecin=m.id_medecin
                                  WHERE r.id_patient=? ORDER BY r.date_rdv_prevue DESC''',
                               (id_patient,)).fetchall()
    ordonnances = db.execute('''SELECT o.*, COUNT(lo.id_ligne) as nb, m.nom_medecin
                                FROM Ordonnance o
                                LEFT JOIN Ligne_Ordonnance lo ON o.id_ordonnance=lo.id_ordonnance
                                JOIN Medecin m ON o.id_medecin=m.id_medecin
                                JOIN Consultation c ON o.id_consultation=c.id_consultation
                                JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                WHERE r.id_patient=? GROUP BY o.id_ordonnance
                                ORDER BY o.date_ordonnance DESC''', (id_patient,)).fetchall()
    return render_template('medecin/dossier_patient.html', patient=patient, dossier=dossier,
                           consultations=consultations, ordonnances=ordonnances)

# ─── PHARMACIEN ───────────────────────────────────────────────────────────────
@app.route('/pharmacien')
@role_required('pharmacien')
def pharmacien_dashboard():
    db = get_db()
    stats = {
        'medicaments': db.execute('SELECT COUNT(*) as c FROM Medicament').fetchone()['c'],
        'ruptures': db.execute('SELECT COUNT(*) as c FROM Inventaire WHERE quantite_dispo <= seuil_alerte').fetchone()['c'],
        'expirations': db.execute("SELECT COUNT(*) as c FROM Inventaire WHERE date_expiration <= date('now','+30 days')").fetchone()['c'],
        'ordonnances': db.execute('SELECT COUNT(*) as c FROM Ordonnance').fetchone()['c'],
    }
    alertes = db.execute('''SELECT i.*, m.nom_medicament FROM Inventaire i
                            JOIN Medicament m ON i.id_medicament=m.id_medicament
                            WHERE i.quantite_dispo <= i.seuil_alerte ORDER BY i.quantite_dispo LIMIT 10''').fetchall()
    return render_template('pharmacien/dashboard.html', stats=stats, alertes=alertes)

@app.route('/pharmacien/medicaments')
@role_required('pharmacien')
def pharmacien_medicaments():
    db = get_db()
    medicaments = db.execute('''SELECT m.*, i.id_inventaire, i.quantite_dispo, i.seuil_alerte,
                                i.date_expiration, i.numero_lot
                                FROM Medicament m LEFT JOIN Inventaire i ON m.id_medicament=i.id_medicament
                                ORDER BY m.nom_medicament''').fetchall()
    return render_template('pharmacien/medicaments.html', medicaments=medicaments)

@app.route('/pharmacien/medicaments/ajouter', methods=['GET', 'POST'])
@role_required('pharmacien')
def pharmacien_ajouter_medicament():
    db = get_db()
    if request.method == 'POST':
        try:
            cur = db.execute('''INSERT INTO Medicament (nom_medicament, description, forme,
                                dosage, categorie, prix) VALUES (?,?,?,?,?,?)''',
                             (request.form['nom'], request.form['description'], request.form['forme'],
                              request.form['dosage'], request.form['categorie'], float(request.form['prix'])))
            id_m = cur.lastrowid
            db.execute('''INSERT INTO Inventaire (quantite_dispo, seuil_alerte, date_expiration,
                          numero_lot, date_peremption, id_medicament) VALUES (?,?,?,?,?,?)''',
                       (int(request.form['quantite']), int(request.form['seuil']),
                        request.form['date_expiration'], request.form['numero_lot'],
                        request.form['date_expiration'], id_m))
            db.commit()
            flash('Médicament ajouté.', 'success')
            return redirect(url_for('pharmacien_medicaments'))
        except Exception as e:
            db.rollback()
            flash(f'Erreur : {e}', 'danger')
    return render_template('pharmacien/ajouter_medicament.html')

@app.route('/pharmacien/stock/modifier/<int:id_inv>', methods=['GET', 'POST'])
@role_required('pharmacien')
def pharmacien_modifier_stock(id_inv):
    db = get_db()
    inv = db.execute('''SELECT i.*, m.nom_medicament FROM Inventaire i
                        JOIN Medicament m ON i.id_medicament=m.id_medicament
                        WHERE i.id_inventaire=?''', (id_inv,)).fetchone()
    if request.method == 'POST':
        db.execute('''UPDATE Inventaire SET quantite_dispo=?, seuil_alerte=?,
                      date_expiration=?, numero_lot=? WHERE id_inventaire=?''',
                   (int(request.form['quantite']), int(request.form['seuil']),
                    request.form['date_expiration'], request.form['numero_lot'], id_inv))
        db.commit()
        flash('Stock mis à jour.', 'success')
        return redirect(url_for('pharmacien_medicaments'))
    return render_template('pharmacien/modifier_stock.html', inv=inv)

@app.route('/pharmacien/ordonnances')
@role_required('pharmacien')
def pharmacien_ordonnances():
    db = get_db()
    ordonnances = db.execute('''SELECT o.*, p.nom_patient, p.prenom_patient, m.nom_medecin,
                                COUNT(lo.id_ligne) as nb_medic
                                FROM Ordonnance o JOIN Medecin m ON o.id_medecin=m.id_medecin
                                JOIN Consultation c ON o.id_consultation=c.id_consultation
                                JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                JOIN Patient p ON r.id_patient=p.id_patient
                                LEFT JOIN Ligne_Ordonnance lo ON o.id_ordonnance=lo.id_ordonnance
                                GROUP BY o.id_ordonnance ORDER BY o.date_ordonnance DESC''').fetchall()
    return render_template('pharmacien/ordonnances.html', ordonnances=ordonnances)

@app.route('/pharmacien/ordonnance/<int:id_ord>')
@role_required('pharmacien')
def pharmacien_detail_ordonnance(id_ord):
    db = get_db()
    ordonnance = db.execute('''SELECT o.*, p.nom_patient, p.prenom_patient, m.nom_medecin
                               FROM Ordonnance o JOIN Medecin m ON o.id_medecin=m.id_medecin
                               JOIN Consultation c ON o.id_consultation=c.id_consultation
                               JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                               JOIN Patient p ON r.id_patient=p.id_patient
                               WHERE o.id_ordonnance=?''', (id_ord,)).fetchone()
    lignes = db.execute('''SELECT lo.*, med.nom_medicament, med.forme, med.dosage, i.quantite_dispo
                           FROM Ligne_Ordonnance lo JOIN Medicament med ON lo.id_medicament=med.id_medicament
                           LEFT JOIN Inventaire i ON med.id_medicament=i.id_medicament
                           WHERE lo.id_ordonnance=?''', (id_ord,)).fetchall()
    return render_template('pharmacien/detail_ordonnance.html', ordonnance=ordonnance, lignes=lignes)

@app.route('/pharmacien/interactions')
@role_required('pharmacien')
def pharmacien_interactions():
    db = get_db()
    interactions = db.execute('''SELECT im.*, m1.nom_medicament as med1, m2.nom_medicament as med2
                                 FROM Interaction_Medicament im
                                 JOIN Medicament m1 ON im.id_med1=m1.id_medicament
                                 JOIN Medicament m2 ON im.id_med2=m2.id_medicament
                                 ORDER BY im.niveau_physique DESC''').fetchall()
    return render_template('pharmacien/interactions.html', interactions=interactions)

# ─── PATIENT ──────────────────────────────────────────────────────────────────
@app.route('/patient')
@role_required('patient')
def patient_dashboard():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    if not patient:
        flash('Profil patient introuvable.', 'danger')
        return redirect(url_for('login'))
    rdvs = db.execute('''SELECT r.*, m.nom_medecin, m.prenom_medecin, m.specialite
                         FROM Rendez_vous r JOIN Medecin m ON r.id_medecin=m.id_medecin
                         WHERE r.id_patient=? AND r.statut_rdv IN ('planifié','confirmé')
                         ORDER BY r.date_rdv_prevue''', (patient['id_patient'],)).fetchall()
    factures = db.execute('''SELECT * FROM Facture WHERE id_patient=? AND statut != 'payée'
                             ORDER BY date_facture DESC LIMIT 5''', (patient['id_patient'],)).fetchall()
    return render_template('patient/dashboard.html', patient=patient, rdvs=rdvs, factures=factures)

@app.route('/patient/dossier')
@role_required('patient')
def patient_dossier():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    dossier = db.execute('SELECT * FROM Dossier_Medical WHERE id_patient=?', (patient['id_patient'],)).fetchone()
    consultations = db.execute('''SELECT c.*, r.date_rdv_prevue, r.motif, m.nom_medecin, m.prenom_medecin
                                  FROM Consultation c JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                  JOIN Medecin m ON c.id_medecin=m.id_medecin
                                  WHERE r.id_patient=? ORDER BY r.date_rdv_prevue DESC''',
                               (patient['id_patient'],)).fetchall()
    return render_template('patient/dossier.html', patient=patient, dossier=dossier, consultations=consultations)

@app.route('/patient/rendez-vous')
@role_required('patient')
def patient_rendez_vous():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    rdvs = db.execute('''SELECT r.*, m.nom_medecin, m.prenom_medecin, m.specialite,
                         s.nom_service, c.nom_centre
                         FROM Rendez_vous r JOIN Medecin m ON r.id_medecin=m.id_medecin
                         JOIN Service_Medical s ON r.id_service=s.id_service
                         JOIN Centre_Medical c ON s.id_centre=c.id_centre
                         WHERE r.id_patient=? ORDER BY r.date_rdv_prevue DESC''',
                      (patient['id_patient'],)).fetchall()
    return render_template('patient/rendez_vous.html', rdvs=rdvs, patient=patient)

@app.route('/patient/rendez-vous/prendre', methods=['GET', 'POST'])
@role_required('patient')
def patient_prendre_rdv():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    if request.method == 'POST':
        db.execute('''INSERT INTO Rendez_vous (date_rdv_prevue, heure, type_rdv, statut_rdv,
                      motif, id_patient, id_medecin, id_service) VALUES (?,?,?,?,?,?,?,?)''',
                   (request.form['date_rdv'], request.form['heure'], request.form['type_rdv'],
                    'planifié', request.form['motif'], patient['id_patient'],
                    request.form['id_medecin'], request.form['id_service']))
        db.commit()
        flash('Rendez-vous pris avec succès.', 'success')
        return redirect(url_for('patient_rendez_vous'))
    medecins = db.execute('SELECT * FROM Medecin').fetchall()
    services = db.execute('''SELECT s.*, c.nom_centre FROM Service_Medical s
                             JOIN Centre_Medical c ON s.id_centre=c.id_centre''').fetchall()
    return render_template('patient/prendre_rdv.html', medecins=medecins, services=services, patient=patient)

@app.route('/patient/ordonnances')
@role_required('patient')
def patient_ordonnances():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    ordonnances = db.execute('''SELECT o.*, m.nom_medecin, m.prenom_medecin, COUNT(lo.id_ligne) as nb
                                FROM Ordonnance o JOIN Medecin m ON o.id_medecin=m.id_medecin
                                JOIN Consultation c ON o.id_consultation=c.id_consultation
                                JOIN Rendez_vous r ON c.id_rdv=r.id_rdv
                                LEFT JOIN Ligne_Ordonnance lo ON o.id_ordonnance=lo.id_ordonnance
                                WHERE r.id_patient=? GROUP BY o.id_ordonnance
                                ORDER BY o.date_ordonnance DESC''', (patient['id_patient'],)).fetchall()
    return render_template('patient/ordonnances.html', ordonnances=ordonnances, patient=patient)

@app.route('/patient/factures')
@role_required('patient')
def patient_factures():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    factures = db.execute('''SELECT f.*, a.nom_compagnie FROM Facture f
                             LEFT JOIN Assurance a ON f.id_assurance=a.id_assurance
                             WHERE f.id_patient=? ORDER BY f.date_facture DESC''',
                          (patient['id_patient'],)).fetchall()
    return render_template('patient/factures.html', factures=factures, patient=patient)

@app.route('/patient/assurances')
@role_required('patient')
def patient_assurances():
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    assurances = db.execute('''SELECT a.* FROM Assurance a
                               JOIN Patient_Assurance pa ON a.id_assurance=pa.id_assurance
                               WHERE pa.id_patient=?''', (patient['id_patient'],)).fetchall()
    toutes = db.execute("SELECT * FROM Assurance WHERE statut='active'").fetchall()
    return render_template('patient/assurances.html', assurances=assurances, toutes=toutes, patient=patient)

@app.route('/patient/assurances/souscrire/<int:id_ass>')
@role_required('patient')
def patient_souscrire_assurance(id_ass):
    db = get_db()
    patient = db.execute('SELECT * FROM Patient WHERE id_utilisateur=?', (session['user_id'],)).fetchone()
    try:
        db.execute('INSERT INTO Patient_Assurance (id_patient, id_assurance) VALUES (?,?)',
                   (patient['id_patient'], id_ass))
        db.commit()
        flash('Souscription enregistrée.', 'success')
    except:
        flash('Déjà souscrit à cette assurance.', 'warning')
    return redirect(url_for('patient_assurances'))

@app.route('/patient/notifications')
@role_required('patient')
def patient_notifications():
    db = get_db()
    notifs = db.execute('''SELECT n.*, nu.etat_lecture FROM Notification n
                           JOIN Notif_Utilisateur nu ON n.id_notification=nu.id_notification
                           WHERE nu.id_utilisateur=? ORDER BY n.date_envoi DESC''',
                        (session['user_id'],)).fetchall()
    db.execute("UPDATE Notif_Utilisateur SET etat_lecture='lu' WHERE id_utilisateur=?",
               (session['user_id'],))
    db.commit()
    return render_template('patient/notifications.html', notifs=notifs)

# ─── ASSUREUR ─────────────────────────────────────────────────────────────────
@app.route('/assureur')
@role_required('assureur')
def assureur_dashboard():
    db = get_db()
    stats = {
        'factures_en_attente': db.execute("SELECT COUNT(*) as c FROM Facture WHERE statut='en attente' AND id_assurance IS NOT NULL").fetchone()['c'],
        'remboursements': db.execute("SELECT COALESCE(SUM(montant_assurance),0) as s FROM Facture WHERE statut='payée'").fetchone()['s'],
        'contrats': db.execute('SELECT COUNT(*) as c FROM Assurance').fetchone()['c'],
        'patients_couverts': db.execute('SELECT COUNT(DISTINCT id_patient) as c FROM Patient_Assurance').fetchone()['c'],
    }
    factures_recentes = db.execute('''SELECT f.*, p.nom_patient, p.prenom_patient, a.nom_compagnie
                                     FROM Facture f JOIN Patient p ON f.id_patient=p.id_patient
                                     LEFT JOIN Assurance a ON f.id_assurance=a.id_assurance
                                     WHERE f.id_assurance IS NOT NULL
                                     ORDER BY f.date_facture DESC LIMIT 10''').fetchall()
    return render_template('assureur/dashboard.html', stats=stats, factures_recentes=factures_recentes)

@app.route('/assureur/factures')
@role_required('assureur')
def assureur_factures():
    db = get_db()
    statut = request.args.get('statut', '')
    query = '''SELECT f.*, p.nom_patient, p.prenom_patient, a.nom_compagnie, a.taux_prise_charge
               FROM Facture f JOIN Patient p ON f.id_patient=p.id_patient
               LEFT JOIN Assurance a ON f.id_assurance=a.id_assurance
               WHERE f.id_assurance IS NOT NULL'''
    params = []
    if statut:
        query += ' AND f.statut=?'
        params.append(statut)
    query += ' ORDER BY f.date_facture DESC'
    factures = db.execute(query, params).fetchall()
    return render_template('assureur/factures.html', factures=factures, statut=statut)

@app.route('/assureur/factures/valider/<int:id_facture>', methods=['GET', 'POST'])
@role_required('assureur')
def assureur_valider_facture(id_facture):
    db = get_db()
    facture = db.execute('''SELECT f.*, p.nom_patient, p.prenom_patient, a.nom_compagnie, a.taux_prise_charge
                            FROM Facture f JOIN Patient p ON f.id_patient=p.id_patient
                            LEFT JOIN Assurance a ON f.id_assurance=a.id_assurance
                            WHERE f.id_facture=?''', (id_facture,)).fetchone()
    if request.method == 'POST':
        m = float(request.form['montant_assurance'])
        mp = facture['montant_total'] - m
        db.execute('''UPDATE Facture SET montant_assurance=?, montant_patient=?,
                      montant_restant=?, statut='payée' WHERE id_facture=?''',
                   (m, mp, mp, id_facture))
        db.commit()
        flash('Remboursement validé.', 'success')
        return redirect(url_for('assureur_factures'))
    return render_template('assureur/valider_facture.html', facture=facture)

@app.route('/assureur/contrats')
@role_required('assureur')
def assureur_contrats():
    db = get_db()
    assurances = db.execute('''SELECT a.*, COUNT(pa.id_patient) as nb_patients
                               FROM Assurance a LEFT JOIN Patient_Assurance pa ON a.id_assurance=pa.id_assurance
                               GROUP BY a.id_assurance ORDER BY a.nom_compagnie''').fetchall()
    return render_template('assureur/contrats.html', assurances=assurances)

@app.route('/assureur/patients-couverts')
@role_required('assureur')
def assureur_patients_couverts():
    db = get_db()
    patients = db.execute('''SELECT p.*, GROUP_CONCAT(a.nom_compagnie) as assurances
                             FROM Patient p JOIN Patient_Assurance pa ON p.id_patient=pa.id_patient
                             JOIN Assurance a ON pa.id_assurance=a.id_assurance
                             GROUP BY p.id_patient ORDER BY p.nom_patient''').fetchall()
    return render_template('assureur/patients_couverts.html', patients=patients)

# ─── API AJAX ─────────────────────────────────────────────────────────────────
@app.route('/api/services')
@login_required
def api_services():
    db = get_db()
    services = db.execute('''SELECT s.id_service, s.nom_service, c.nom_centre
                             FROM Service_Medical s
                             JOIN Centre_Medical c ON s.id_centre=c.id_centre''').fetchall()
    return jsonify([dict(s) for s in services])

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
