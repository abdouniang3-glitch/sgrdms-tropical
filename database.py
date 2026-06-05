import sqlite3
import os
from flask import g
import hashlib

DATABASE = 'sgrdms.db'

def get_db():
    from flask import current_app
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db

def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Create all tables and seed demo data."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # ── TABLES ──────────────────────────────────────────────────────────────
    c.executescript("""
    CREATE TABLE IF NOT EXISTS Utilisateur (
        id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
        login          VARCHAR(50)  NOT NULL UNIQUE,
        mot_de_passe   VARCHAR(255) NOT NULL,
        role           VARCHAR(20)  NOT NULL
        CHECK (role IN ('admin','medecin','pharmacien','patient','secretaire','assureur'))
    );

    CREATE TABLE IF NOT EXISTS Patient (
        id_patient      INTEGER     PRIMARY KEY AUTOINCREMENT,
        nom_patient     VARCHAR(100) NOT NULL,
        prenom_patient  VARCHAR(100) NOT NULL,
        date_naissance  DATE,
        sexe            CHAR(1)  CHECK (sexe IN ('M','F','A')),
        telephone       VARCHAR(20),
        adresse         TEXT,
        mail            VARCHAR(150) UNIQUE,
        id_utilisateur  INTEGER UNIQUE REFERENCES Utilisateur(id_utilisateur) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS Medecin (
        id_medecin        INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_medecin       VARCHAR(100) NOT NULL,
        prenom_medecin    VARCHAR(100) NOT NULL,
        telephone         VARCHAR(20),
        email             VARCHAR(150),
        specialite        VARCHAR(100),
        actif_teleconsult BOOLEAN DEFAULT 0,
        disponibilite     TEXT,
        id_utilisateur    INTEGER UNIQUE REFERENCES Utilisateur(id_utilisateur) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS Centre_Medical (
        id_centre      INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_centre     VARCHAR(150) NOT NULL,
        adresse_centre TEXT,
        type_centre    VARCHAR(50),
        telephone      VARCHAR(20),
        ville          VARCHAR(100)
    );

    CREATE TABLE IF NOT EXISTS Service_Medical (
        id_service  INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_service VARCHAR(100),
        id_centre   INTEGER NOT NULL REFERENCES Centre_Medical(id_centre) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS Medecin_Centre (
        id_medecin INTEGER NOT NULL REFERENCES Medecin(id_medecin) ON DELETE CASCADE,
        id_centre  INTEGER NOT NULL REFERENCES Centre_Medical(id_centre) ON DELETE CASCADE,
        PRIMARY KEY (id_medecin, id_centre)
    );

    CREATE TABLE IF NOT EXISTS Dossier_Medical (
        id_dossier     INTEGER PRIMARY KEY AUTOINCREMENT,
        date_creation  DATE,
        antecedents    TEXT,
        allergies      TEXT,
        groupe_sanguin VARCHAR(5),
        notes          TEXT,
        id_patient     INTEGER NOT NULL UNIQUE REFERENCES Patient(id_patient) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS Rendez_vous (
        id_rdv          INTEGER PRIMARY KEY AUTOINCREMENT,
        date_rdv_prevue DATETIME,
        date_rdv_reelle DATETIME,
        heure           TIME,
        type_rdv        VARCHAR(30),
        statut_rdv      VARCHAR(20),
        motif           TEXT,
        id_patient      INTEGER NOT NULL REFERENCES Patient(id_patient),
        id_medecin      INTEGER NOT NULL REFERENCES Medecin(id_medecin),
        id_service      INTEGER NOT NULL REFERENCES Service_Medical(id_service)
    );

    CREATE TABLE IF NOT EXISTS Consultation (
        id_consultation  INTEGER PRIMARY KEY AUTOINCREMENT,
        statut           VARCHAR(20),
        observations     TEXT,
        heure            TIME,
        diagnostic       TEXT,
        constantes_vital TEXT,
        id_medecin       INTEGER NOT NULL REFERENCES Medecin(id_medecin),
        id_rdv           INTEGER NOT NULL UNIQUE REFERENCES Rendez_vous(id_rdv),
        id_dossier       INTEGER NOT NULL REFERENCES Dossier_Medical(id_dossier)
    );

    CREATE TABLE IF NOT EXISTS Teleconsultation (
        id_session      INTEGER PRIMARY KEY AUTOINCREMENT,
        url_video       TEXT,
        duree           INTEGER,
        heure           DATETIME,
        statut          VARCHAR(20),
        enregistrement  BOOLEAN DEFAULT 0,
        id_medecin      INTEGER NOT NULL REFERENCES Medecin(id_medecin),
        id_consultation INTEGER UNIQUE REFERENCES Consultation(id_consultation) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS Liste_Attente (
        id_attente       INTEGER PRIMARY KEY AUTOINCREMENT,
        date_inscription DATETIME,
        priorite         VARCHAR(20),
        statut           VARCHAR(20),
        id_patient       INTEGER NOT NULL REFERENCES Patient(id_patient),
        id_centre        INTEGER NOT NULL REFERENCES Centre_Medical(id_centre),
        id_rdv           INTEGER REFERENCES Rendez_vous(id_rdv)
    );

    CREATE TABLE IF NOT EXISTS Medicament (
        id_medicament  INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_medicament VARCHAR(150) NOT NULL,
        description    TEXT,
        forme          VARCHAR(50),
        dosage         VARCHAR(50),
        categorie      VARCHAR(100),
        prix           DECIMAL(10,2)
    );

    CREATE TABLE IF NOT EXISTS Ordonnance (
        id_ordonnance   INTEGER PRIMARY KEY AUTOINCREMENT,
        date_ordonnance DATE,
        validite        VARCHAR(50),
        instructions    TEXT,
        id_medecin      INTEGER NOT NULL REFERENCES Medecin(id_medecin),
        id_consultation INTEGER NOT NULL REFERENCES Consultation(id_consultation)
    );

    CREATE TABLE IF NOT EXISTS Ligne_Ordonnance (
        id_ligne         INTEGER PRIMARY KEY AUTOINCREMENT,
        date_delivrance  DATE,
        posologie        VARCHAR(100),
        duree_traitement INTEGER,
        quantite         INTEGER,
        nombre_medic     INTEGER,
        id_ordonnance    INTEGER NOT NULL REFERENCES Ordonnance(id_ordonnance),
        id_medicament    INTEGER NOT NULL REFERENCES Medicament(id_medicament)
    );

    CREATE TABLE IF NOT EXISTS Inventaire (
        id_inventaire   INTEGER PRIMARY KEY AUTOINCREMENT,
        quantite_dispo  INTEGER,
        seuil_alerte    INTEGER,
        date_expiration DATE,
        numero_lot      VARCHAR(50),
        date_peremption DATE,
        id_medicament   INTEGER NOT NULL REFERENCES Medicament(id_medicament)
    );

    CREATE TABLE IF NOT EXISTS Interaction_Medicament (
        id_med1         INTEGER NOT NULL REFERENCES Medicament(id_medicament),
        id_med2         INTEGER NOT NULL REFERENCES Medicament(id_medicament),
        niveau_physique VARCHAR(20),
        alerte          TEXT,
        PRIMARY KEY (id_med1, id_med2),
        CHECK (id_med1 < id_med2)
    );

    CREATE TABLE IF NOT EXISTS Assurance (
        id_assurance      INTEGER PRIMARY KEY AUTOINCREMENT,
        nom_compagnie     VARCHAR(150),
        numero_contrat    VARCHAR(50),
        taux_prise_charge DECIMAL(5,2),
        type_assurance    VARCHAR(50),
        date_debut        DATE,
        fin_couverture    DATE,
        statut            VARCHAR(20),
        plafond_annuel    DECIMAL(12,2),
        statut_tiers_pay  BOOLEAN DEFAULT 0,
        type_prise_charge VARCHAR(50)
    );

    CREATE TABLE IF NOT EXISTS Patient_Assurance (
        id_patient   INTEGER NOT NULL REFERENCES Patient(id_patient) ON DELETE CASCADE,
        id_assurance INTEGER NOT NULL REFERENCES Assurance(id_assurance) ON DELETE CASCADE,
        PRIMARY KEY (id_patient, id_assurance)
    );

    CREATE TABLE IF NOT EXISTS Facture (
        id_facture        INTEGER PRIMARY KEY AUTOINCREMENT,
        date_facture      DATE,
        montant_total     DECIMAL(12,2),
        montant_patient   DECIMAL(12,2),
        montant_assurance DECIMAL(12,2),
        montant_restant   DECIMAL(12,2),
        statut            VARCHAR(20),
        id_patient        INTEGER NOT NULL REFERENCES Patient(id_patient),
        id_consultation   INTEGER NOT NULL UNIQUE REFERENCES Consultation(id_consultation),
        id_assurance      INTEGER REFERENCES Assurance(id_assurance)
    );

    CREATE TABLE IF NOT EXISTS Notification (
        id_notification INTEGER PRIMARY KEY AUTOINCREMENT,
        type_notif      VARCHAR(50),
        contenu         TEXT,
        date_envoi      DATETIME,
        heure_creation  TIME,
        etat            VARCHAR(10) DEFAULT 'non lu',
        id_facture      INTEGER NOT NULL REFERENCES Facture(id_facture)
    );

    CREATE TABLE IF NOT EXISTS Notif_Utilisateur (
        id_notification INTEGER NOT NULL REFERENCES Notification(id_notification) ON DELETE CASCADE,
        id_utilisateur  INTEGER NOT NULL REFERENCES Utilisateur(id_utilisateur) ON DELETE CASCADE,
        date_reception  DATETIME,
        etat_lecture    VARCHAR(10) DEFAULT 'non lu',
        PRIMARY KEY (id_notification, id_utilisateur)
    );

    CREATE TABLE IF NOT EXISTS Historique (
        id_historique   INTEGER PRIMARY KEY AUTOINCREMENT,
        date_action     DATETIME,
        type_action     VARCHAR(30),
        description     TEXT,
        action          TEXT,
        id_utilisateur  INTEGER NOT NULL REFERENCES Utilisateur(id_utilisateur),
        id_consultation INTEGER REFERENCES Consultation(id_consultation),
        id_ordonnance   INTEGER REFERENCES Ordonnance(id_ordonnance),
        id_notification INTEGER REFERENCES Notification(id_notification)
    );
    """)
    conn.commit()

    # ── SEED DATA ────────────────────────────────────────────────────────────
    def hp(p): return hashlib.sha256(p.encode()).hexdigest()

    existing = c.execute("SELECT COUNT(*) FROM Utilisateur").fetchone()[0]
    if existing == 0:
        # Utilisateurs
        users = [
            ('admin',       hp('admin123'),       'admin'),
            ('dr.diallo',   hp('medecin123'),      'medecin'),
            ('dr.ba',       hp('medecin123'),      'medecin'),
            ('pharma1',     hp('pharma123'),       'pharmacien'),
            ('patient1',    hp('patient123'),      'patient'),
            ('patient2',    hp('patient123'),      'patient'),
            ('assureur1',   hp('assureur123'),     'assureur'),
            ('secretaire1', hp('secret123'),       'secretaire'),
        ]
        c.executemany('INSERT INTO Utilisateur (login, mot_de_passe, role) VALUES (?,?,?)', users)

        # Centre & services
        c.execute("INSERT INTO Centre_Medical (nom_centre, adresse_centre, type_centre, telephone, ville) VALUES ('Centre de Santé LE TROPICAL','Avenue Léopold Sédar Senghor, Thiès','clinique','+221 33 951 00 00','Thiès')")
        id_centre = c.lastrowid
        services = [('Médecine Générale', id_centre), ('Pédiatrie', id_centre),
                    ('Cardiologie', id_centre), ('Urgences', id_centre), ('Téléconsultation', id_centre)]
        c.executemany('INSERT INTO Service_Medical (nom_service, id_centre) VALUES (?,?)', services)

        # Médecins
        c.execute("INSERT INTO Medecin (nom_medecin, prenom_medecin, telephone, email, specialite, actif_teleconsult, disponibilite, id_utilisateur) VALUES ('Diallo','Amadou','+221 77 123 45 67','diallo@tropical.sn','Médecine Générale',1,'Lun-Ven 08h-17h',2)")
        id_med1 = c.lastrowid
        c.execute("INSERT INTO Medecin (nom_medecin, prenom_medecin, telephone, email, specialite, actif_teleconsult, disponibilite, id_utilisateur) VALUES ('Ba','Fatou','+221 77 234 56 78','ba@tropical.sn','Cardiologie',1,'Lun-Mer 09h-16h',3)")
        id_med2 = c.lastrowid
        c.execute('INSERT INTO Medecin_Centre VALUES (?,?)', (id_med1, id_centre))
        c.execute('INSERT INTO Medecin_Centre VALUES (?,?)', (id_med2, id_centre))

        # Patients
        c.execute("INSERT INTO Patient (nom_patient, prenom_patient, date_naissance, sexe, telephone, adresse, mail, id_utilisateur) VALUES ('Ndiaye','Ibrahima','1985-03-15','M','+221 77 345 67 89','Quartier Liberté, Thiès','ibrahima.ndiaye@email.com',5)")
        id_p1 = c.lastrowid
        c.execute("INSERT INTO Dossier_Medical (date_creation, antecedents, allergies, groupe_sanguin, notes, id_patient) VALUES (date('now'),'Hypertension artérielle','Pénicilline','A+','Suivi régulier requis',?)", (id_p1,))

        c.execute("INSERT INTO Patient (nom_patient, prenom_patient, date_naissance, sexe, telephone, adresse, mail, id_utilisateur) VALUES ('Sarr','Mariama','1992-07-22','F','+221 77 456 78 90','Cité Lamy, Thiès','mariama.sarr@email.com',6)")
        id_p2 = c.lastrowid
        c.execute("INSERT INTO Dossier_Medical (date_creation, antecedents, allergies, groupe_sanguin, notes, id_patient) VALUES (date('now'),'Diabète type 2','Aspirine','O+','Régime alimentaire strict',?)", (id_p2,))

        # Médicaments + stock
        meds = [
            ('Paracétamol 500mg','Antalgique et antipyrétique','Comprimé','500mg','Antalgique',150),
            ('Amoxicilline 500mg','Antibiotique à large spectre','Gélule','500mg','Antibiotique',500),
            ('Métformine 850mg','Antidiabétique oral','Comprimé','850mg','Antidiabétique',800),
            ('Amlodipine 5mg','Antihypertenseur','Comprimé','5mg','Cardiovasculaire',600),
            ('Ibuprofène 400mg','Anti-inflammatoire non stéroïdien','Comprimé','400mg','AINS',300),
        ]
        med_ids = []
        for m in meds:
            c.execute("INSERT INTO Medicament (nom_medicament, description, forme, dosage, categorie, prix) VALUES (?,?,?,?,?,?)", m)
            med_ids.append(c.lastrowid)

        import datetime
        exp = (datetime.date.today().replace(year=datetime.date.today().year+2)).isoformat()
        stocks = [(200,20,exp,'LOT2026A'),(150,15,exp,'LOT2026B'),(100,10,exp,'LOT2026C'),
                  (80,8,exp,'LOT2026D'),(5,10,exp,'LOT2026E')]  # 5 = alerte rupture
        for i, (q,s,d,l) in enumerate(stocks):
            c.execute("INSERT INTO Inventaire (quantite_dispo, seuil_alerte, date_expiration, numero_lot, date_peremption, id_medicament) VALUES (?,?,?,?,?,?)",
                      (q,s,d,l,d,med_ids[i]))

        # Interaction médicamenteuse
        c.execute("INSERT INTO Interaction_Medicament (id_med1, id_med2, niveau_physique, alerte) VALUES (?,?,'élevé','Association déconseillée : risque de saignement augmenté')",
                  (med_ids[0], med_ids[4]))

        # Assurance
        c.execute("INSERT INTO Assurance (nom_compagnie, numero_contrat, taux_prise_charge, type_assurance, date_debut, fin_couverture, statut, plafond_annuel, statut_tiers_pay, type_prise_charge) VALUES ('INAM Sénégal','CONT-2026-001',80.0,'maladie','2026-01-01','2026-12-31','active',1500000,1,'Soins courants')")
        id_ass = c.lastrowid
        c.execute('INSERT INTO Patient_Assurance VALUES (?,?)', (id_p1, id_ass))

        # RDV + Consultation + Ordonnance exemple
        c.execute("INSERT INTO Rendez_vous (date_rdv_prevue, date_rdv_reelle, heure, type_rdv, statut_rdv, motif, id_patient, id_medecin, id_service) VALUES (datetime('now','-1 day'), datetime('now','-1 day'), '09:00', 'présentiel', 'effectué', 'Fièvre persistante', ?, ?, 1)",
                  (id_p1, id_med1))
        id_rdv = c.lastrowid
        id_dossier = c.execute('SELECT id_dossier FROM Dossier_Medical WHERE id_patient=?', (id_p1,)).fetchone()[0]
        c.execute("INSERT INTO Consultation (statut, observations, heure, diagnostic, constantes_vital, id_medecin, id_rdv, id_dossier) VALUES ('terminée','Patient fébrile à 38.5°C, gorge rouge','09:15','Angine bactérienne','T:38.5°C, TA:120/80, Pouls:82',?,?,?)",
                  (id_med1, id_rdv, id_dossier))
        id_consult = c.lastrowid
        c.execute("INSERT INTO Ordonnance (date_ordonnance, validite, instructions, id_medecin, id_consultation) VALUES (date('now'),'3 mois','Prendre les médicaments avec de l eau',?,?)",
                  (id_med1, id_consult))
        id_ord = c.lastrowid
        c.execute("INSERT INTO Ligne_Ordonnance (posologie, duree_traitement, quantite, nombre_medic, id_ordonnance, id_medicament) VALUES ('3 fois/jour',7,21,1,?,?)",
                  (id_ord, med_ids[1]))
        c.execute("INSERT INTO Facture (date_facture, montant_total, montant_patient, montant_assurance, montant_restant, statut, id_patient, id_consultation, id_assurance) VALUES (date('now'),15000,3000,12000,3000,'en attente',?,?,?)",
                  (id_p1, id_consult, id_ass))

        conn.commit()
        print("✅ Base de données initialisée avec données de démonstration.")
    else:
        print("✅ Base de données déjà existante.")

    conn.close()
