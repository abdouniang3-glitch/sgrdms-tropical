# SGRDMS — Système de Gestion du Centre LE TROPICAL

## Installation & Lancement (VS Code)

### 1. Prérequis
- Python 3.8+ installé
- VS Code avec extension Python

### 2. Installation des dépendances
Ouvrir le terminal dans VS Code (Ctrl+`) et exécuter :

```bash
pip install flask
```

### 3. Lancer l'application
```bash
python run.py
```

### 4. Accéder à l'application
Ouvrir le navigateur : http://127.0.0.1:5000

---

## Comptes de démonstration

| Login        | Mot de passe | Rôle         |
|--------------|--------------|--------------|
| admin        | admin123     | Administrateur |
| dr.diallo    | medecin123   | Médecin       |
| dr.ba        | medecin123   | Médecin       |
| pharma1      | pharma123    | Pharmacien    |
| patient1     | patient123   | Patient       |
| patient2     | patient123   | Patient       |
| assureur1    | assureur123  | Assureur      |
| secretaire1  | secret123    | Secrétaire    |

---

## Structure du projet

```
sgrdms/
├── run.py              ← Point d'entrée
├── app.py              ← Routes Flask
├── database.py         ← BDD SQLite + initialisation
├── sgrdms.db           ← Base de données (créée au 1er lancement)
├── requirements.txt
└── templates/
    ├── base.html
    ├── auth/login.html
    ├── admin/          ← 9 vues admin
    ├── medecin/        ← 6 vues médecin
    ├── pharmacien/     ← 7 vues pharmacien
    ├── patient/        ← 8 vues patient
    └── assureur/       ← 5 vues assureur
```

## Fonctionnalités par acteur

### Administrateur
- Tableau de bord avec statistiques
- Gestion des utilisateurs (CRUD)
- Gestion des patients (avec dossier médical + compte)
- Gestion des médecins
- Gestion des centres médicaux
- Gestion des assurances
- Planification des rendez-vous
- Journal d'audit (historique)

### Médecin
- Tableau de bord + RDV du jour
- Agenda complet
- Saisie des consultations (constantes, observations, diagnostic)
- Émission d'ordonnances multi-médicaments
- Téléconsultations
- Dossiers patients

### Pharmacien
- Tableau de bord avec alertes rupture
- Gestion médicaments + stock
- Consultation des ordonnances
- Détail par ordonnance (stocks disponibles)
- Interactions médicamenteuses

### Patient (Portail patient)
- Tableau de bord personnel
- Dossier médical
- Prise de rendez-vous
- Suivi des ordonnances
- Consultation des factures
- Gestion des assurances
- Notifications

### Assureur
- Tableau de bord remboursements
- Liste et filtrage des factures
- Validation des remboursements
- Contrats d'assurance
- Patients couverts
