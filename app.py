from datetime import datetime
from email.message import EmailMessage
import smtplib
import sqlite3
import pandas as pd
import streamlit as st

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Suivi Flotte - Entreprise", page_icon="🚗", layout="wide"
)

DB_NAME = "fleet_data.db"

# --- LISTE OFFICIELLE DES COLLABORATEURS ---
LISTE_EQUIPE = [
    "Nathalie",
    "Amélie",
    "Sophie",
    "Amina",
    "Eugénie",
    "Cyrille",
    "Martine",
    "Dominique",
    "Joana",
    "Stéphane",
    "Pauline",
    "Chloé",
]

# --- CODE PIN D'ACCÈS ---
CODE_SECRET = (
    st.secrets["APP_PASSWORD"] if "APP_PASSWORD" in st.secrets else "1234"
)


# --- FONCTION D'ENVOI D'E-MAIL (ROBUSTE ET ISOLÉE) ---
def envoyer_alerte_email(sujet, corps_message):
  if (
      "EMAIL_USER" not in st.secrets
      or "EMAIL_PASSWORD" not in st.secrets
      or "EMAIL_REFERENT" not in st.secrets
  ):
    st.warning(
        "⚠️ Clés e-mail manquantes dans secrets.toml (EMAIL_USER,"
        " EMAIL_PASSWORD, EMAIL_REFERENT)."
    )
    return

  smtp_server = "smtp.gmail.com"
  port = 465

  sender_email = st.secrets["EMAIL_USER"]
  sender_password = st.secrets["EMAIL_PASSWORD"]
  destinataire = st.secrets["EMAIL_REFERENT"]

  msg = EmailMessage()
  msg.set_content(corps_message)
  msg["Subject"] = sujet
  msg["From"] = sender_email
  msg["To"] = destinataire

  with smtplib.SMTP_SSL(smtp_server, port, timeout=5) as server:
    server.login(sender_email, sender_password)
    server.send_message(msg)

  st.success("E-mail réel envoyé avec succès !")


# --- AUTHENTIFICATION ---
if "authentifie" not in st.session_state:
  st.session_state.authentifie = False

if not st.session_state.authentifie:
  st.title("🔒 Accès Restreint - Gestion de Flotte")
  code_saisi = st.text_input("Code d'accès de l'équipe", type="password")
  if st.button("Valider"):
    if code_saisi == CODE_SECRET:
      st.session_state.authentifie = True
      st.rerun()
    else:
      st.error("Code incorrect.")
  st.stop()


# --- INITIALISATION DE LA BASE DE DONNÉES ---
def init_db():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            immatriculation TEXT UNIQUE,
            modele TEXT,
            conducteur TEXT,
            prochain_ct TEXT,
            km_actuel INTEGER,
            km_prochaine_revision INTEGER,
            carburant_pct INTEGER,
            statut TEXT
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS trajets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            conducteur TEXT,
            immatriculation TEXT,
            destination TEXT,
            km_enregistre INTEGER,
            carburant_pct INTEGER
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            immatriculation TEXT,
            signale_par TEXT,
            type_probleme TEXT,
            description TEXT,
            statut TEXT
        )
    """)

  cursor.execute("SELECT COUNT(*) FROM vehicles")
  if cursor.fetchone()[0] == 0:
    initial_vehicles = [
        ("GE-684-QE", "Renault Clio 6", "Pool", "2027-03-15", 12500, 15000, 100, "En service"),
        ("GZ-018-XF", "Renault Captur", "Pool", "2026-10-10", 28000, 30000, 75, "En service"),
        ("EL-485-NG", "Renault Clio 5", "Pool", "2026-09-25", 44500, 45000, 50, "En service"),
    ]
    cursor.executemany("""
            INSERT INTO vehicles (immatriculation, modele, conducteur, prochain_ct, km_actuel, km_prochaine_revision, carburant_pct, statut)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_vehicles)
    conn.commit()

  conn.close()


init_db()

# --- INTERFACE UTILISATEUR (SIDEBAR) ---
st.sidebar.title("🚗 Navigation")
if st.sidebar.button("Se déconnecter"):
  st.session_state.authentifie = False
  st.rerun()

menu = st.sidebar.selectbox(
    "Aller vers",
    [
        "📝 Saisie Trajet & Km (Accueil)",
        "📊 Tableau de Bord & Alertes",
        "📋 Historique des Trajets (PV / Contrôles)",
        "🚙 Parc de Véhicules",
        "🚨 Signaler un Incident",
    ],
)


# --- PAGE 1 : SAISIE TRAJET & KM (ACCUEIL PRINCIPAL UX) ---
if menu == "📝 Saisie Trajet & Km (Accueil)":
  st.title("🚗 Enregistrement de Trajet & Véhicule")
  st.write(
      "Indique ton déplacement pour mettre à jour automatiquement le compteur"
      " et tracer le trajet."
  )

  conn = sqlite3.connect(DB_NAME)
  df_vehicles = pd.read_sql("SELECT * FROM vehicles", conn)
  conn.close()

  with st.form("trajet_form"):
    col1, col2 = st.columns(2)
    with col1:
      immat_km = st.selectbox(
          "Véhicule", df_vehicles["immatriculation"].tolist()
      )
      conducteur = st.selectbox("Conducteur", LISTE_EQUIPE)
    with col2:
      destination = st.text_input(
          "Destination / Motif du déplacement",
          placeholder="Ex: Client / Chantier X",
      )

    current_row = df_vehicles.loc[df_vehicles["immatriculation"] == immat_km].iloc[0]
    current_km = int(current_row["km_actuel"])
    current_carbu = int(current_row["carburant_pct"])

    st.divider()
    col3, col4 = st.columns(2)
    with col3:
      nouveau_km = st.number_input(
          "Nouveau kilométrage au compteur",
          min_value=current_km,
          value=current_km,
          step=1,
      )
    with col4:
      nouveau_carbu = st.slider(
          "Niveau de carburant / Batterie (%)", 0, 100, current_carbu
      )

    submit_trajet = st.form_submit_button(
        "Enregistrer le trajet et les relevés", use_container_width=True
    )

    if submit_trajet:
      if not destination:
        st.warning("Veuillez indiquer une destination ou un motif.")
      else:
        date_jour = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            """
                    UPDATE vehicles 
                    SET km_actuel = ?, carburant_pct = ?, conducteur = ? 
                    WHERE immatriculation = ?
                """,
            (nouveau_km, nouveau_carbu, conducteur, immat_km),
        )

        cursor.execute(
            """
                    INSERT INTO trajets (date, conducteur, immatriculation, destination, km_enregistre, carburant_pct)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
            (
                date_jour,
                conducteur,
                immat_km,
                destination,
                nouveau_km,
                nouveau_carbu,
            ),
        )

        cursor.execute(
            "SELECT km_prochaine_revision, modele FROM vehicles WHERE"
            " immatriculation = ?",
            (immat_km,),
        )
        res = cursor.fetchone()
        conn.commit()
        conn.close()

        seuil_rev = res[0]
        modele = res[1]
        restant = seuil_rev - nouveau_km

        st.success(
            f"Trajet enregistré avec succès pour **{conducteur}** sur la"
            f" **{modele}** ({immat_km}) !"
        )

        if restant <= 1000:
          st.warning(
              f"🚨 **Alerte Révision :** Il reste {restant} km avant la"
              f" révision ({seuil_rev} km)."
          )
        st.rerun()


# --- PAGE 2 : TABLEAU DE BORD & ALERTES ---
elif menu == "📊 Tableau de Bord & Alertes":
  st.title("📊 Tableau de Bord - Suivi Flotte")

  conn = sqlite3.connect(DB_NAME)
  df_vehicles = pd.read_sql("SELECT * FROM vehicles", conn)
  df_incidents = pd.read_sql("SELECT * FROM incidents WHERE statut != 'Résolu'", conn)
  conn.close()

  col1, col2, col3 = st.columns(3)
  col1.metric("Véhicules suivis", len(df_vehicles))
  col2.metric("Incidents en cours", len(df_incidents))

  today = datetime.now().date()
  alert_count = 0
  for _, row in df_vehicles.iterrows():
    ct_date = datetime.strptime(row["prochain_ct"], "%Y-%m-%d").date()
    km_restants = row["km_prochaine_revision"] - row["km_actuel"]
    if (ct_date - today).days <= 30 or km_restants <= 1000:
      alert_count += 1
  col3.metric("Alertes Entretien / CT", alert_count)

  st.divider()
  st.subheader("⚠️ Alertes à traiter")
  alerts_list = []
  for _, row in df_vehicles.iterrows():
    ct_date = datetime.strptime(row["prochain_ct"], "%Y-%m-%d").date()
    km_restants = row["km_prochaine_revision"] - row["km_actuel"]

    if (ct_date - today).days <= 30:
      alerts_list.append({
          "Immat": row["immatriculation"],
          "Modèle": row["modele"],
          "Alerte": "CT Proche",
          "Détail": row["prochain_ct"],
      })
    if km_restants <= 1000:
      status_km = "Dépassé !" if km_restants < 0 else f"Reste {km_restants} km"
      alerts_list.append({
          "Immat": row["immatriculation"],
          "Modèle": row["modele"],
          "Alerte": "Révision imminente",
          "Détail": status_km,
      })

  if alerts_list:
    st.dataframe(pd.DataFrame(alerts_list), use_container_width=True)
  else:
    st.success("Aucune alerte critique !")

  st.subheader("🛠️ Incidents en cours")
  if not df_incidents.empty:
    st.dataframe(df_incidents, use_container_width=True)
  else:
    st.info("Aucun incident en cours.")


# --- PAGE 3 : HISTORIQUE DES TRAJETS ---
elif menu == "📋 Historique des Trajets (PV / Contrôles)":
  st.title("📋 Historique des Trajets & Conducteurs")
  st.write(
      "Registre utile en cas de contrôle, d'amende (PV) ou pour auditer les"
      " déplacements par conducteur."
  )

  conn = sqlite3.connect(DB_NAME)
  df_trajets = pd.read_sql("SELECT * FROM trajets ORDER BY id DESC", conn)
  conn.close()

  if not df_trajets.empty:
    conducteur_filtre = st.selectbox(
        "Filtrer par conducteur", ["Tous"] + LISTE_EQUIPE
    )
    if conducteur_filtre != "Tous":
      df_trajets = df_trajets[df_trajets["conducteur"] == conducteur_filtre]

    st.dataframe(df_trajets, use_container_width=True)
  else:
    st.info("Aucun trajet enregistré pour le moment.")


# --- PAGE 4 : PARC DE VÉHICULES ---
elif menu == "🚙 Parc de Véhicules":
  st.title("🚙 État Actuel du Parc")

  conn = sqlite3.connect(DB_NAME)
  df_vehicles = pd.read_sql("SELECT * FROM vehicles", conn)
  conn.close()

  st.dataframe(df_vehicles, use_container_width=True)


# --- PAGE 5 : SIGNALER UN INCIDENT ---
elif menu == "🚨 Signaler un Incident":
  st.title("🚨 Signaler un Incident")

  conn = sqlite3.connect(DB_NAME)
  df_vehicles = pd.read_sql("SELECT * FROM vehicles", conn)
  conn.close()

  if df_vehicles.empty:
    st.warning("Aucun véhicule trouvé dans la base de données.")
  else:
    with st.form("incident_form"):
      immat = st.selectbox(
          "Véhicule concerné", df_vehicles["immatriculation"].tolist()
      )
      signale_par = st.selectbox("Votre nom (Conducteur)", LISTE_EQUIPE)
      type_prob = st.selectbox(
          "Type de problème",
          [
              "Pneumatique (ex: pneu dégonflé/crevé)",
              "Mécanique / Voyant moteur",
              "Carrosserie / Choc",
              "Propreté / Autre",
          ],
      )
      description = st.text_area("Description précise du problème")

      submit_incident = st.form_submit_button(
          "Envoyer le signalement", use_container_width=True
      )

      if submit_incident:
        if not description.strip():
          st.warning("Veuillez remplir la description.")
        else:
          try:
            date_jour = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()

            cursor.execute(
                """
                            INSERT INTO incidents (date, immatriculation, signale_par, type_probleme, description, statut)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """,
                (
                    date_jour,
                    immat,
                    signale_par,
                    type_prob,
                    description,
                    "En cours",
                ),
            )

            cursor.execute(
                """
                            UPDATE vehicles SET statut = ? WHERE immatriculation = ?
                        """,
                ("En maintenance / Incident", immat),
            )

            conn.commit()
            conn.close()
            st.success(
                "Incident enregistré en base de données avec succès !"
            )

            try:
              envoyer_alerte_email(
                  sujet=f"⚠️ INCIDENT FLOTTE - {immat} ({type_prob})",
                  corps_message=(
                      f"Bonjour,\n\n{signale_par} vient de signaler un"
                      f" incident sur le véhicule {immat}.\n\n- Type :"
                      f" {type_prob}\n- Description : {description}\n\nLe"
                      " véhicule est passé en statut 'En maintenance'."
                  ),
              )
            except Exception as mail_err:
              st.info(
                  "Note : L'incident a bien été noté, mais l'e-mail automatique"
                  f" n'a pas pu partir ({mail_err})."
              )

          except Exception as db_err:
            st.error(
                "Erreur lors de l'enregistrement dans la base de données :"
                f" {db_err}"
            )