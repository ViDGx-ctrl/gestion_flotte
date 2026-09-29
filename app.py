from datetime import datetime
from email.message import EmailMessage
import smtplib
import pandas as pd
import streamlit as st
from sqlalchemy import text

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Suivi Flotte - Entreprise", page_icon="🚗", layout="wide"
)

# --- CONNEXION POSTGRESQL / SUPABASE ---
conn = st.connection("postgresql", type="sql")

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


# --- FONCTION D'ENVOI D'E-MAIL ---
def envoyer_alerte_email(sujet, corps_message):
  if (
      "EMAIL_USER" not in st.secrets
      or "EMAIL_PASSWORD" not in st.secrets
      or "EMAIL_REFERENT" not in st.secrets
  ):
    st.warning("⚠️ Clés e-mail manquantes dans secrets.toml.")
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


# --- INITIALISATION DE LA BASE POSTGRESQL ---
def init_db():
  with conn.session as session:
    session.execute(text("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id SERIAL PRIMARY KEY,
                immatriculation VARCHAR(50) UNIQUE,
                modele VARCHAR(100),
                conducteur VARCHAR(100),
                prochain_ct VARCHAR(50),
                km_actuel INTEGER,
                km_prochaine_revision INTEGER,
                carburant_pct INTEGER,
                statut VARCHAR(50)
            );
        """))

    session.execute(text("""
            CREATE TABLE IF NOT EXISTS trajets (
                id SERIAL PRIMARY KEY,
                date VARCHAR(50),
                conducteur VARCHAR(100),
                immatriculation VARCHAR(50),
                destination VARCHAR(255),
                km_enregistre INTEGER,
                carburant_pct INTEGER
            );
        """))

    session.execute(text("""
            CREATE TABLE IF NOT EXISTS incidents (
                id SERIAL PRIMARY KEY,
                date VARCHAR(50),
                immatriculation VARCHAR(50),
                signale_par VARCHAR(100),
                type_probleme VARCHAR(100),
                description TEXT,
                statut VARCHAR(50)
            );
        """))
    session.commit()

  # Si la table est vide, insertion des valeurs initiales
  count_df = conn.query("SELECT COUNT(*) as cnt FROM vehicles", ttl=0)
  if count_df.iloc[0]["cnt"] == 0:
    with conn.session as session:
      initial_vehicles = [
          ("GE-684-QE", "Renault Clio 6", "Pool", "2027-03-15", 12500, 15000, 100, "En service"),
          ("GZ-018-XF", "Renault Captur", "Pool", "2026-10-10", 28000, 30000, 75, "En service"),
          ("EL-485-NG", "Renault Clio 5", "Pool", "2026-09-25", 44500, 45000, 50, "En service"),
      ]
      for v in initial_vehicles:
        session.execute(
            text("""
                INSERT INTO vehicles (immatriculation, modele, conducteur, prochain_ct, km_actuel, km_prochaine_revision, carburant_pct, statut)
                VALUES (:immat, :modele, :conducteur, :prochain_ct, :km_actuel, :km_rev, :carbu, :statut)
                ON CONFLICT (immatriculation) DO NOTHING;
            """),
            {
                "immat": v[0],
                "modele": v[1],
                "conducteur": v[2],
                "prochain_ct": v[3],
                "km_actuel": v[4],
                "km_rev": v[5],
                "carbu": v[6],
                "statut": v[7],
            },
        )
      session.commit()


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


# --- PAGE 1 : SAISIE TRAJET & KM ---
if menu == "📝 Saisie Trajet & Km (Accueil)":
  st.title("🚗 Enregistrement de Trajet & Véhicule")
  st.write(
      "Indique ton déplacement pour mettre à jour automatiquement le compteur"
      " et tracer le trajet."
  )

  df_vehicles = conn.query("SELECT * FROM vehicles ORDER BY immatriculation", ttl=0)

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
        with conn.session as session:
          session.execute(
              text("""
                    UPDATE vehicles 
                    SET km_actuel = :km, carburant_pct = :carbu, conducteur = :conducteur 
                    WHERE immatriculation = :immat
                """),
              {
                  "km": nouveau_km,
                  "carbu": nouveau_carbu,
                  "conducteur": conducteur,
                  "immat": immat_km,
              },
          )

          session.execute(
              text("""
                    INSERT INTO trajets (date, conducteur, immatriculation, destination, km_enregistre, carburant_pct)
                    VALUES (:date, :conducteur, :immat, :destination, :km, :carbu)
                """),
              {
                  "date": date_jour,
                  "conducteur": conducteur,
                  "immat": immat_km,
                  "destination": destination,
                  "km": nouveau_km,
                  "carbu": nouveau_carbu,
              },
          )
          session.commit()

        seuil_rev = int(current_row["km_prochaine_revision"])
        modele = current_row["modele"]
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

  df_vehicles = conn.query("SELECT * FROM vehicles ORDER BY immatriculation", ttl=0)
  df_incidents = conn.query("SELECT * FROM incidents WHERE statut != 'Résolu' ORDER BY id DESC", ttl=0)

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
          "Détail": str(row["prochain_ct"]),
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

  df_trajets = conn.query("SELECT * FROM trajets ORDER BY id DESC", ttl=0)

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
  df_vehicles = conn.query("SELECT * FROM vehicles ORDER BY immatriculation", ttl=0)
  st.dataframe(df_vehicles, use_container_width=True)


# --- PAGE 5 : SIGNALER UN INCIDENT ---
elif menu == "🚨 Signaler un Incident":
  st.title("🚨 Signaler un Incident")

  df_vehicles = conn.query("SELECT * FROM vehicles ORDER BY immatriculation", ttl=0)

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
            with conn.session as session:
              session.execute(
                  text("""
                        INSERT INTO incidents (date, immatriculation, signale_par, type_probleme, description, statut)
                        VALUES (:date, :immat, :signale_par, :type_probleme, :description, :statut)
                    """),
                  {
                      "date": date_jour,
                      "immat": immat,
                      "signale_par": signale_par,
                      "type_probleme": type_prob,
                      "description": description,
                      "statut": "En cours",
                  },
              )
              session.execute(
                  text("""
                        UPDATE vehicles SET statut = :statut WHERE immatriculation = :immat
                    """),
                  {"statut": "En maintenance / Incident", "immat": immat},
              )
              session.commit()

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
