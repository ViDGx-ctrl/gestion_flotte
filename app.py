from datetime import datetime
from email.message import EmailMessage
import smtplib
from dateutil.relativedelta import relativedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import text

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Suivi Flotte - Entreprise", page_icon="🚗", layout="wide"
)

# --- CODE PIN D'ACCÈS ---
CODE_SECRET = str(
    st.secrets["APP_PASSWORD"] if "APP_PASSWORD" in st.secrets else "1234"
)

# --- LISTE OFFICIELLE DES COLLABORATEURS ---
LISTE_EQUIPE = [
    "Vincent",
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

# ==============================================================================
# 1. AUTHENTIFICATION PAR CHAMP OPTIMISÉ MOBILE (ZÉRO LATENCE RÉSEAU)
# ==============================================================================
if "authentifie" not in st.session_state:
  st.session_state.authentifie = False

if not st.session_state.authentifie:
  st.markdown("### 🔒 Accès Restreint")
  st.caption("Saisis le code PIN de l'équipe pour déverrouiller l'accès.")

  st.markdown(
      """
        <style>
        div[data-testid="stTextInput"] input {
            font-size: 32px !important;
            letter-spacing: 12px !important;
            text-align: center !important;
            height: 65px !important;
            border-radius: 12px !important;
        }
        div.stButton > button {
            height: 55px !important;
            font-size: 18px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
        }
        </style>
    """,
      unsafe_allow_html=True,
  )

  components.html(
      """
        <script>
        const inputs = window.parent.document.querySelectorAll('input[type="password"]');
        inputs.forEach(input => {
            input.setAttribute('inputmode', 'numeric');
            input.setAttribute('pattern', '[0-9]*');
        });
        </script>
    """,
      height=0,
      width=0,
  )

  with st.form("form_pin_rapide"):
    code_saisi = st.text_input(
        "Code PIN",
        type="password",
        max_chars=6,
        placeholder="••••",
        label_visibility="collapsed",
    )
    btn_valider = st.form_submit_button(
        "Déverrouiller l'accès", use_container_width=True
    )

    if btn_valider:
      if str(code_saisi).strip() == CODE_SECRET:
        st.session_state.authentifie = True
        st.rerun()
      else:
        st.error("Code PIN incorrect.")

  st.stop()

# ==============================================================================
# 2. CONNEXION BDD & INITIALISATION
# ==============================================================================
conn = st.connection("postgresql", type="sql")


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


@st.cache_resource
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
                date_prochaine_revision VARCHAR(50),
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


init_db()


def get_vehicule_options(df):
  if df.empty:
    return {}
  return {f"{r['immatriculation']} — {r['modele']}": r["immatriculation"] for _, r in df.iterrows()}


# --- BARRE SUPÉRIEURE : NAVIGATION EN PLEINE PAGE ---
col_nav, col_logout = st.columns([4, 1])
with col_nav:
  section_principale = st.radio(
      "Navigation",
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
# SECTION 1 : SAISIE TRAJET & INCIDENT (USAGE TERRAIN)
# ==============================================================================
if section_principale == "🚗 Saisie Trajet & Incident":
  tab_trajet, tab_incident = st.tabs(
      ["📝 Enregistrer un trajet", "🚨 Signaler un incident"]
  )

  # --- SOUS-ONGLET 1 : SAISIE DU TRAJET ---
  with tab_trajet:
    st.subheader("Enregistrement de déplacement")
    df_vehicles = conn.query(
        "SELECT * FROM vehicles ORDER BY immatriculation", ttl=5
    )

    if df_vehicles.empty:
      st.warning("⚠️ Aucun véhicule enregistré dans la base.")
    else:
      veh_options = get_vehicule_options(df_vehicles)

      selected_label = st.selectbox(
          "Véhicule", list(veh_options.keys()), key="select_trajet_vehicule"
      )
      immat_km = veh_options[selected_label]

      current_row = df_vehicles.loc[
          df_vehicles["immatriculation"] == immat_km
      ].iloc[0]
      current_km = int(current_row["km_actuel"])
      current_carbu = int(current_row["carburant_pct"])

      with st.form("trajet_form"):
        col1, col2 = st.columns(2)
        with col1:
          conducteur = st.selectbox("Conducteur", LISTE_EQUIPE)
        with col2:
          destination = st.text_input(
              "Destination / Motif du déplacement",
              placeholder="Ex: Rendez-vous client / Chantier",
          )

        st.markdown(
            f"**Compteur actuel ({current_row['modele']}) :** `{current_km} km`"
        )

        col3, col4 = st.columns(2)
        with col3:
          nouveau_km = st.number_input(
              "Nouveau kilométrage au compteur",
              min_value=current_km,
              value=current_km,
              step=1,
              key=f"km_input_{immat_km}",
          )
        with col4:
          nouveau_carbu = st.slider(
              "Niveau carburant / batterie (%)",
              0,
              100,
              current_carbu,
              key=f"carbu_input_{immat_km}",
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
        "SELECT * FROM vehicles ORDER BY immatriculation", ttl=5
    )

    if df_vehicles.empty:
      st.warning("⚠️ Aucun véhicule enregistré dans la base.")
    else:
      veh_options = get_vehicule_options(df_vehicles)

      with st.form("incident_form"):
        selected_label = st.selectbox(
            "Véhicule concerné", list(veh_options.keys()), key="immat_incident"
        )
        immat = veh_options[selected_label]
        modele = df_vehicles.loc[
            df_vehicles["immatriculation"] == immat
        ].iloc[0]["modele"]

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
                    sujet=(
                        f"⚠️ INCIDENT FLOTTE - {immat} ({modele}) - {type_prob}"
                    ),
                    corps_message=(
                        f"Bonjour,\n\n{signale_par} vient de signaler un"
                        f" incident sur {modele} ({immat}).\n\n- Type :"
                        f" {type_prob}\n- Description : {description}\n\nLe"
                        " véhicule a été placé sous le statut 'En maintenance'."
                    ),
                )
              except Exception as mail_err:
                st.info(
                    "Note : Incident enregistré, mais notification non"
                    f" transmise ({mail_err})."
                )

              st.rerun()
            except Exception as db_err:
              st.error(f"Erreur d'enregistrement : {db_err}")

# ==============================================================================
# SECTION 2 : SUIVI ET ADMINISTRATION (REGROUPEMENT ERGONOMIQUE)
# ==============================================================================
elif section_principale == "⚙️ Suivi & Administration":
  st.subheader("Administration & Pilotage de la flotte")

  tab_gestion, tab_historique = st.tabs(
      ["🚗 Gestion & Entretien du Parc", "📋 Historique des trajets"]
  )

  df_vehicles = conn.query(
      "SELECT * FROM vehicles ORDER BY immatriculation", ttl=5
  )
  df_incidents = conn.query(
      "SELECT * FROM incidents WHERE statut != 'Résolu' ORDER BY id DESC",
      ttl=5,
  )
  veh_options = get_vehicule_options(df_vehicles)
  today = datetime.now().date()

  # --------------------------------------------------------------------------
  # ONGLET 1 : GESTION DU PARC (SYNTHÈSE + ALERTES + ACTIONS SUR LE VÉHICULE)
  # --------------------------------------------------------------------------
  with tab_gestion:
    # 1. Chiffres clés
    c1, c2, c3 = st.columns(3)
    c1.metric("Véhicules suivis", len(df_vehicles))
    c2.metric("Incidents en cours", len(df_incidents))

    alert_count = 0
    if not df_vehicles.empty:
      for _, row in df_vehicles.iterrows():
        ct_date = datetime.strptime(str(row["prochain_ct"]), "%Y-%m-%d").date()
        ct_alerte = (ct_date - today).days <= 30
        km_restants = row["km_prochaine_revision"] - row["km_actuel"]
        km_alerte = km_restants <= 1000

        date_rev_str = row.get("date_prochaine_revision")
        date_rev_alerte = False
        if date_rev_str and pd.notna(date_rev_str):
          rev_date = datetime.strptime(str(date_rev_str), "%Y-%m-%d").date()
          date_rev_alerte = (rev_date - today).days <= 30

        if ct_alerte or km_alerte or date_rev_alerte:
          alert_count += 1
    c3.metric("Alertes Révision / CT", alert_count)

    # 2. Alertes immédiates avec validation rapide
    st.markdown("#### 🚨 Échéances à traiter en priorité")
    alertes_trouvees = False

    if not df_vehicles.empty:
      for _, row in df_vehicles.iterrows():
        immat = row["immatriculation"]
        modele = row["modele"]
        km_actuel = int(row["km_actuel"])
        km_rev = int(row["km_prochaine_revision"])
        ct_date = datetime.strptime(str(row["prochain_ct"]), "%Y-%m-%d").date()
        km_restants = km_rev - km_actuel

        date_rev_str = row.get("date_prochaine_revision")
        rev_date = None
        date_rev_alerte = False
        jours_rev_restants = 999
        if date_rev_str and pd.notna(date_rev_str):
          rev_date = datetime.strptime(str(date_rev_str), "%Y-%m-%d").date()
          jours_rev_restants = (rev_date - today).days
          date_rev_alerte = jours_rev_restants <= 30

        # Alerte Révision (km OU 1 an)
        if km_restants <= 1000 or date_rev_alerte:
          alertes_trouvees = True
          raisons = []
          if km_restants <= 1000:
            raisons.append(
                f"Kilométrage atteint ({km_actuel} km / seuil {km_rev} km)"
            )
          if date_rev_alerte and rev_date:
            detail_delai = (
                f"dépassée de {abs(jours_rev_restants)} jour(s)"
                if jours_rev_restants < 0
                else f"dans {jours_rev_restants} jour(s)"
            )
            raisons.append(
                f"Échéance 1 an ({rev_date.strftime('%d/%m/%Y')} -"
                f" {detail_delai})"
            )

          col_info, col_btn = st.columns([3, 2])
          with col_info:
            motif_txt = " • ".join(raisons)
            st.error(
                f"🔧 **{immat} — {modele}** | **Révision requise**\n\n{motif_txt}"
            )
          with col_btn:
            nouvelle_cible_km = km_actuel + 20000
            nouvelle_date_rev = today + relativedelta(years=1)
            if st.button(
                "Marquer faite (+20 000 km & +1 an)",
                key=f"btn_done_rev_{immat}",
            ):
              with conn.session as session:
                session.execute(
                    text("""
                                  UPDATE vehicles 
                                  SET km_prochaine_revision = :cible_km, 
                                      date_prochaine_revision = :cible_date,
                                      statut = 'En service' 
                                  WHERE immatriculation = :immat
                              """),
                    {
                        "cible_km": nouvelle_cible_km,
                        "cible_date": nouvelle_date_rev.strftime("%Y-%m-%d"),
                        "immat": immat,
                    },
                )
                session.commit()
              st.success(f"Révision validée pour {immat} !")
              st.rerun()

        # Alerte Contrôle Technique
        if (ct_date - today).days <= 30:
          alertes_trouvees = True
          col_info, col_btn = st.columns([3, 2])
          with col_info:
            jours_restants = (ct_date - today).days
            detail_ct = (
                f"Expiré depuis {abs(jours_restants)} jour(s) !"
                if jours_restants < 0
                else f"Expire dans {jours_restants} jour(s)"
            )
            st.warning(
                f"🛡️ **{immat} — {modele}** | **Contrôle"
                f" Technique**\n\nDate limite : {ct_date.strftime('%d/%m/%Y')}"
                f" ({detail_ct})"
            )
          with col_btn:
            nouveau_ct = today + relativedelta(years=2)
            if st.button(f"Marquer fait (+2 ans)", key=f"btn_done_ct_{immat}"):
              with conn.session as session:
                session.execute(
                    text("""
                                  UPDATE vehicles 
                                  SET prochain_ct = :date_ct 
                                  WHERE immatriculation = :immat
                              """),
                    {
                        "date_ct": nouveau_ct.strftime("%Y-%m-%d"),
                        "immat": immat,
                    },
                )
                session.commit()
              st.success(f"CT validé pour {immat} (+2 ans) !")
              st.rerun()

    if not alertes_trouvees:
      st.success("✅ Aucune échéance critique d'entretien ou de CT à traiter.")

    # 3. Incidents signalés
    st.markdown("#### 🛠️ Incidents signalés")
    if not df_incidents.empty:
      for _, inc in df_incidents.iterrows():
        mod_trouve = df_vehicles.loc[
            df_vehicles["immatriculation"] == inc["immatriculation"]
        ]
        nom_mod = mod_trouve.iloc[0]["modele"] if not mod_trouve.empty else ""

        col_desc, col_act = st.columns([4, 1])
        with col_desc:
          st.warning(
              f"**{inc['immatriculation']} — {nom_mod}** |"
              f" {inc['type_probleme']}\n\n*Signalé par {inc['signale_par']} le"
              f" {inc['date']}* : {inc['description']}"
          )
        with col_act:
          if st.button("Marquer résolu", key=f"res_{inc['id']}"):
            with conn.session as session:
              session.execute(
                  text(
                      "UPDATE incidents SET statut = 'Résolu' WHERE id = :id"
                  ),
                  {"id": inc["id"]},
              )
              session.execute(
                  text("""
                                  UPDATE vehicles SET statut = 'En service' 
                                  WHERE immatriculation = :immat 
                                  AND NOT EXISTS (
                                      SELECT 1 FROM incidents WHERE immatriculation = :immat AND statut = 'En cours'
                                  )
                              """),
                  {"immat": inc["immatriculation"]},
              )
              session.commit()
            st.rerun()
    else:
      st.info("Aucun incident ouvert.")

    st.divider()

    # 4. Fiche d'actions par véhicule (Entretien détaillé & Corrections)
    st.markdown("#### ⚙️ Actions & Mise à jour d'un véhicule")
    if not df_vehicles.empty:
      selected_label_admin = st.selectbox(
          "Sélectionner le véhicule à mettre à jour",
          list(veh_options.keys()),
          key="select_admin_vehicule",
      )
      immat_admin = veh_options[selected_label_admin]
      veh_admin = df_vehicles.loc[
          df_vehicles["immatriculation"] == immat_admin
      ].iloc[0]

      exp_rev, exp_ct, exp_corr = st.tabs([
          "🛠️ Révision d'atelier",
          "🛡️ Contrôle Technique",
          "✏️️ Correction km & Statut",
      ])

      # Sous-onglet A : Révision avec détails facture
      with exp_rev:
        st.caption("Enregistrer le kilométrage et la date réels de la facture.")
        with st.form("form_revision_admin"):
          col_r1, col_r2 = st.columns(2)
          with col_r1:
            km_facture = st.number_input(
                "Kilométrage de la révision (km)",
                value=int(veh_admin["km_actuel"]),
                step=100,
                key=f"fac_km_{immat_admin}",
            )
          with col_r2:
            date_facture = st.date_input(
                "Date de la révision",
                value=today,
                key=f"fac_date_{immat_admin}",
            )

          cible_km = km_facture + 20000
          cible_date = date_facture + relativedelta(years=1)
          st.info(
              f"👉 Prochain seuil calculé : **{cible_km} km** ou"
              f" **{cible_date.strftime('%d/%m/%Y')}** (+1 an)"
          )

          if st.form_submit_button(
              "Valider la révision", use_container_width=True
          ):
            with conn.session as session:
              session.execute(
                  text("""
                                UPDATE vehicles 
                                SET km_prochaine_revision = :cible_km, 
                                    date_prochaine_revision = :cible_date,
                                    km_actuel = :km, 
                                    statut = 'En service' 
                                WHERE immatriculation = :immat
                            """),
                  {
                      "cible_km": cible_km,
                      "cible_date": cible_date.strftime("%Y-%m-%d"),
                      "km": km_facture,
                      "immat": immat_admin,
                  },
              )
              session.commit()
            st.success(f"Révision enregistrée pour {selected_label_admin} !")
            st.rerun()

      # Sous-onglet B : CT avec date personnalisée
      with exp_ct:
        st.caption("Mettre à jour la date précise du passage au CT (+2 ans).")
        with st.form("form_ct_admin"):
          date_ct = st.date_input(
              "Date effective du contrôle",
              value=today,
              key=f"ct_date_{immat_admin}",
          )
          cible_ct = date_ct + relativedelta(years=2)
          st.info(
              f"👉 Prochain CT calculé au :"
              f" **{cible_ct.strftime('%d/%m/%Y')}** (+2 ans)"
          )

          if st.form_submit_button(
              "Valider le passage au CT", use_container_width=True
          ):
            with conn.session as session:
              session.execute(
                  text("""
                                UPDATE vehicles 
                                SET prochain_ct = :date_ct 
                                WHERE immatriculation = :immat
                            """),
                  {
                      "date_ct": cible_ct.strftime("%Y-%m-%d"),
                      "immat": immat_admin,
                  },
              )
              session.commit()
            st.success(f"Contrôle technique mis à jour pour {immat_admin} !")
            st.rerun()

      # Sous-onglet C : Correction manuelle du compteur et statut
      with exp_corr:
        st.caption(
            "Corriger une erreur de saisie ou ajuster le statut opérationnel."
        )
        with st.form("form_corr_admin"):
          col_c1, col_c2 = st.columns(2)
          with col_c1:
            km_corr = st.number_input(
                "Kilométrage réel au compteur (km)",
                value=int(veh_admin["km_actuel"]),
                step=50,
                key=f"corr_km_{immat_admin}",
            )
          with col_c2:
            statut_corr = st.selectbox(
                "Statut actuel",
                ["En service", "En maintenance / Incident"],
                index=(0 if veh_admin["statut"] == "En service" else 1),
                key=f"corr_statut_{immat_admin}",
            )

          if st.form_submit_button(
              "Enregistrer les modifications", use_container_width=True
          ):
            with conn.session as session:
              session.execute(
                  text("""
                                UPDATE vehicles 
                                SET km_actuel = :km, statut = :statut 
                                WHERE immatriculation = :immat
                            """),
                  {
                      "km": km_corr,
                      "statut": statut_corr,
                      "immat": immat_admin,
                  },
              )
              session.commit()
            st.success(f"Données mises à jour pour {immat_admin} !")
            st.rerun()

    st.divider()
    st.markdown("#### 🚙 Parc complet en base")
    st.dataframe(df_vehicles, use_container_width=True)

  # --------------------------------------------------------------------------
  # ONGLET 2 : HISTORIQUE COMPLET DES DÉPLACEMENTS
  # --------------------------------------------------------------------------
  with tab_historique:
    st.markdown("#### 📋 Registre des déplacements")
    df_trajets = conn.query("SELECT * FROM trajets ORDER BY id DESC", ttl=5)

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
