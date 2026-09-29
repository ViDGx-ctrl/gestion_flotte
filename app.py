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
    st.warning("⚠️ Paramètres e-mail manquants dans les secrets.")
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

  st.success("E-mail d'alerte envoyé avec succès !")


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

  count_df = conn.query("SELECT COUNT(*) as cnt FROM vehicles", ttl=0)
  if count_df.iloc[0]["cnt"] == 0:
    with conn.session as session:
      initial_vehicles = [
          ("GE-684-QE", "Renault Clio 6", "Pool", "2027-03-15", 74000, 94000, 100, "En service"),
          ("GZ-018-XF", "Renault Captur", "Pool", "2026-10-10", 28000, 48000, 75, "En service"),
          ("EL-485-NG", "Renault Clio 5", "Pool", "2026-09-25", 44500, 64500, 50, "En service"),
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

# --- BARRE SUPÉRIEURE : NAVIGATION PLEINE PAGE ---
col_nav, col_logout = st.columns([4, 1])
with col_nav:
  section_principale = st.radio(
      "Menu de navigation",
      ["🚗 Saisie Trajet & Incident", "⚙️ Suivi & Administration"],
      horizontal=True,
      label_visibility="collapsed",
  )
with col_logout:
  if st.button("Déconnexion", use_container_width=True):
    st.session_state.authentifie = False
    st.rerun()

st.divider()

# ==============================================================================
# SECTION 1 : SAISIE TRAJET & INCIDENT (USAGE QUOTIDIEN TERRAIN)
# ==============================================================================
if section_principale == "🚗 Saisie Trajet & Incident":
  tab_trajet, tab_incident = st.tabs(
      ["📝 Enregistrer un trajet", "🚨 Signaler un incident"]
  )

  # --- SOUS-ONGLET 1 : SAISIE TRAJET ---
  with tab_trajet:
    st.subheader("Enregistrement de déplacement")
    df_vehicles = conn.query(
        "SELECT * FROM vehicles ORDER BY immatriculation", ttl=0
    )

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
            placeholder="Ex: Rendez-vous client / Chantier",
        )

      current_row = df_vehicles.loc[
          df_vehicles["immatriculation"] == immat_km
      ].iloc[0]
      current_km = int(current_row["km_actuel"])
      current_carbu = int(current_row["carburant_pct"])

      st.markdown(f"**Kilométrage actuel relevé :** `{current_km} km`")

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
            "Niveau carburant / batterie (%)", 0, 100, current_carbu
        )

      submit_trajet = st.form_submit_button(
          "Enregistrer le trajet", use_container_width=True
      )

      if submit_trajet:
        if not destination.strip():
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
              f"Trajet validé pour {conducteur} ({modele} - {immat_km}) !"
          )
          if restant <= 1000:
            st.warning(
                f"🚨 **Alerte Révision :** Il reste {restant} km avant la"
                f" révision ({seuil_rev} km)."
            )
          st.rerun()

  # --- SOUS-ONGLET 2 : SIGNALEMENT INCIDENT ---
  with tab_incident:
    st.subheader("Déclarer un problème ou un incident")
    df_vehicles = conn.query(
        "SELECT * FROM vehicles ORDER BY immatriculation", ttl=0
    )

    with st.form("incident_form"):
      immat = st.selectbox(
          "Véhicule concerné",
          df_vehicles["immatriculation"].tolist(),
          key="immat_incident",
      )
      signale_par = st.selectbox(
          "Votre nom", LISTE_EQUIPE, key="conducteur_incident"
      )
      type_prob = st.selectbox(
          "Type de problème",
          [
              "Pneumatique (ex: pneu dégonflé/crevé)",
              "Mécanique / Voyant moteur",
              "Carrosserie / Choc",
              "Propreté / Autre",
          ],
      )
      description = st.text_area("Description du problème constaté")

      submit_incident = st.form_submit_button(
          "Envoyer l'alerte incident", use_container_width=True
      )

      if submit_incident:
        if not description.strip():
          st.warning("Veuillez décrire le problème.")
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

            st.success("Incident enregistré en base !")

            try:
              envoyer_alerte_email(
                  sujet=f"⚠️ INCIDENT FLOTTE - {immat} ({type_prob})",
                  corps_message=(
                      f"Bonjour,\n\n{signale_par} vient de signaler un"
                      f" incident sur le véhicule {immat}.\n\n- Type :"
                      f" {type_prob}\n- Description : {description}\n\nLe"
                      " véhicule est sous statut 'En maintenance'."
                  ),
              )
            except Exception as mail_err:
              st.info(
                  "Note : Incident enregistré, mais notification e-mail non"
                  f" envoyée ({mail_err})."
              )

            st.rerun()
          except Exception as db_err:
            st.error(f"Erreur d'enregistrement : {db_err}")

# ==============================================================================
# SECTION 2 : SUIVI ET ADMINISTRATION
# ==============================================================================
elif section_principale == "⚙️ Suivi & Administration":
  st.subheader("Tableau de bord et administration")

  tab_pilotage, tab_maintenance, tab_correction, tab_historique = st.tabs([
      "📊 Alertes & Synthèse",
      "🛠️ Révision effectuée",
      "✏️ Correction km & Statut",
      "📋 Historique trajets",
  ])

  df_vehicles = conn.query(
      "SELECT * FROM vehicles ORDER BY immatriculation", ttl=0
  )
  df_incidents = conn.query(
      "SELECT * FROM incidents WHERE statut != 'Résolu' ORDER BY id DESC", ttl=0
  )

  # --- SOUS-ONGLET 1 : SYNTHÈSE & ALERTES ---
  with tab_pilotage:
    c1, c2, c3 = st.columns(3)
    c1.metric("Véhicules suivis", len(df_vehicles))
    c2.metric("Incidents en cours", len(df_incidents))

    today = datetime.now().date()
    alert_count = 0
    for _, row in df_vehicles.iterrows():
      ct_date = datetime.strptime(str(row["prochain_ct"]), "%Y-%m-%d").date()
      km_restants = row["km_prochaine_revision"] - row["km_actuel"]
      if (ct_date - today).days <= 30 or km_restants <= 1000:
        alert_count += 1
    c3.metric("Alertes Révision / CT", alert_count)

    st.markdown("#### 🚨 Échéances à surveiller")
    alerts_list = []
    for _, row in df_vehicles.iterrows():
      ct_date = datetime.strptime(str(row["prochain_ct"]), "%Y-%m-%d").date()
      km_restants = row["km_prochaine_revision"] - row["km_actuel"]

      if (ct_date - today).days <= 30:
        alerts_list.append({
            "Immatriculation": row["immatriculation"],
            "Modèle": row["modele"],
            "Type d'alerte": "CT Proche",
            "Échéance": str(row["prochain_ct"]),
        })
      if km_restants <= 1000:
        detail_km = (
            "Dépassement révision !"
            if km_restants < 0
            else f"Reste {km_restants} km"
        )
        alerts_list.append({
            "Immatriculation": row["immatriculation"],
            "Modèle": row["modele"],
            "Type d'alerte": "Révision imminente",
            "Échéance": detail_km,
        })

    if alerts_list:
      st.dataframe(pd.DataFrame(alerts_list), use_container_width=True)
    else:
      st.success("Aucune alerte d'entretien critique.")

    st.markdown("#### 🛠️ Incidents signalés en cours")
    if not df_incidents.empty:
      st.dataframe(df_incidents, use_container_width=True)
    else:
      st.info("Aucun incident ouvert.")

  # --- SOUS-ONGLET 2 : VALIDER UNE RÉVISION EFFECTUÉE ---
  with tab_maintenance:
    st.markdown("#### 🛠️ Enregistrer une révision effectuée chez le garagiste")
    st.caption(
        "Repousse automatiquement la prochaine révision de +20 000 km à partir"
        " du kilométrage réel de sortie d'atelier."
    )

    immat_rev = st.selectbox(
        "Véhicule révisé",
        df_vehicles["immatriculation"].tolist(),
        key="immat_rev_select",
    )
    v_rev = df_vehicles.loc[
        df_vehicles["immatriculation"] == immat_rev
    ].iloc[0]

    with st.form("form_revision_done"):
      km_facture = st.number_input(
          "Kilométrage exact lors de la révision (km)",
          value=int(v_rev["km_actuel"]),
          step=100,
      )
      prochaine_cible = km_facture + 20000
      st.info(f"👉 Prochain palier calculé : **{prochaine_cible} km** (+20 000 km)")

      submit_rev = st.form_submit_button(
          "Valider la révision et réinitialiser l'alerte",
          use_container_width=True,
      )

      if submit_rev:
        with conn.session as session:
          session.execute(
              text("""
                    UPDATE vehicles 
                    SET km_prochaine_revision = :cible, km_actuel = :km, statut = 'En service' 
                    WHERE immatriculation = :immat
                """),
              {"cible": prochaine_cible, "km": km_facture, "immat": immat_rev},
          )
          session.commit()
        st.success(
            f"Révision enregistrée pour {immat_rev} ! Prochaine échéance fixée à"
            f" {prochaine_cible} km."
        )
        st.rerun()

  # --- SOUS-ONGLET 3 : CORRECTION COMPTEUR & STATUT ---
  with tab_correction:
    st.markdown("#### ✏️ Corriger manuellement le compteur")
    st.caption("Utile en cas d'erreur de frappe ou d'oubli d'un collaborateur.")

    immat_select = st.selectbox(
        "Sélectionner le véhicule",
        df_vehicles["immatriculation"].tolist(),
        key="select_ajust_immat",
    )
    selected_veh = df_vehicles.loc[
        df_vehicles["immatriculation"] == immat_select
    ].iloc[0]

    with st.form("ajustement_km_form"):
      col_adj1, col_adj2 = st.columns(2)
      with col_adj1:
        nouveau_km_reel = st.number_input(
            "Kilométrage réel (km)",
            value=int(selected_veh["km_actuel"]),
            step=50,
        )
      with col_adj2:
        statut_veh = st.selectbox(
            "Statut du véhicule",
            ["En service", "En maintenance / Incident"],
            index=(0 if selected_veh["statut"] == "En service" else 1),
        )

      submit_ajust = st.form_submit_button(
          "Mettre à jour", use_container_width=True
      )

      if submit_ajust:
        with conn.session as session:
          session.execute(
              text("""
                    UPDATE vehicles 
                    SET km_actuel = :km, statut = :statut 
                    WHERE immatriculation = :immat
                """),
              {
                  "km": nouveau_km_reel,
                  "statut": statut_veh,
                  "immat": immat_select,
              },
          )
          session.commit()
        st.success(f"{immat_select} mis à jour à {nouveau_km_reel} km !")
        st.rerun()

    st.divider()
    st.markdown("#### 🚙 Parc complet")
    st.dataframe(df_vehicles, use_container_width=True)

  # --- SOUS-ONGLET 4 : HISTORIQUE DES TRAJETS ---
  with tab_historique:
    st.markdown("#### 📋 Registre des déplacements")
    df_trajets = conn.query("SELECT * FROM trajets ORDER BY id DESC", ttl=0)

    if not df_trajets.empty:
      filtre_cond = st.selectbox(
          "Filtrer par collaborateur",
          ["Tous"] + LISTE_EQUIPE,
          key="filtre_historique",
      )
      if filtre_cond != "Tous":
        df_trajets = df_trajets[df_trajets["conducteur"] == filtre_cond]
      st.dataframe(df_trajets, use_container_width=True)
    else:
      st.info("Aucun trajet enregistré dans la base.")
