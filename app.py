# --- AUTHENTIFICATION PAR PAVÉ NUMÉRIQUE COMPACT ---
if "authentifie" not in st.session_state:
  st.session_state.authentifie = False
if "pin_saisi" not in st.session_state:
  st.session_state.pin_saisi = ""

if not st.session_state.authentifie:
  # CSS pour forcer la grille 3x3 sur smartphone sans empilement vertical
  st.markdown(
      """
        <style>
        [data-testid="column"] {
            flex: 1 1 calc(33.333% - 1rem) !important;
            min-width: 0 !important;
        }
        div.stButton > button {
            height: 60px !important;
            font-size: 24px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
        }
        </style>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("### 🔒 Accès Restreint")
  st.caption("Code PIN de l'équipe :")

  nb_chiffres = len(st.session_state.pin_saisi)
  affichage_code = "● " * nb_chiffres if nb_chiffres > 0 else "Entrez le code"
  st.markdown(
      f"<div style='text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 6px; padding: 12px; background-color: #1e293b; color: #f8fafc; border-radius: 10px; margin-bottom: 15px;'>{affichage_code}</div>",
      unsafe_allow_html=True,
  )

  touches = [
      ["1", "2", "3"],
      ["4", "5", "6"],
      ["7", "8", "9"],
      ["⌫", "0", "OK"],
  ]

  for ligne in touches:
    cols = st.columns(3)
    for i, touche in enumerate(ligne):
      with cols[i]:
        if st.button(
            touche, key=f"btn_pin_{touche}", use_container_width=True
        ):
          if touche == "⌫":
            st.session_state.pin_saisi = st.session_state.pin_saisi[:-1]
            st.rerun()
          elif touche == "OK":
            if st.session_state.pin_saisi == CODE_SECRET:
              st.session_state.authentifie = True
              st.session_state.pin_saisi = ""
              st.rerun()
            else:
              st.error("Code PIN incorrect.")
              st.session_state.pin_saisi = ""
              st.rerun()
          else:
            if len(st.session_state.pin_saisi) < 8:
              st.session_state.pin_saisi += touche
              st.rerun()

  st.stop()
