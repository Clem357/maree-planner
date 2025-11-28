import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from ics import Calendar, Event
import pytz # <-- NÉCESSAIRE pour la gestion correcte de l'heure d'été/hiver (Europe/Paris)

# --- CONFIGURATION & DONNÉES ---
st.set_page_config(page_title="Calendrier Marées (Stable)", page_icon="🌊", layout="centered")

# LECTURE AUTOMATIQUE DE LA CLÉ DE L'API DEPUIS LE COFFRE-FORT DE STREAMLIT (secrets.toml)
# La clé doit être enregistrée sous la variable 'WORLDTIDES_KEY'
try:
    API_KEY = st.secrets["WORLDTIDES_KEY"]
except KeyError:
    API_KEY = None
    st.error(
        "🛑 Clé API manquante. Veuillez ajouter votre clé WorldTides "
        "dans le fichier secrets.toml de Streamlit sous la variable WORLDTIDES_KEY."
    )


# Base de données des lieux (Lat/Lon pour l'API)
# Liste complète des ports français majeurs
PORTS_DB = {
    "--- MANCHE EST ---": None,
    "Dunkerque": {"lat": 51.0504, "lon": 2.3768},
    "Calais": {"lat": 50.9513, "lon": 1.8587},
    "Boulogne-sur-Mer": {"lat": 50.7259, "lon": 1.5976},
    "Le Havre": {"lat": 49.4944, "lon": 0.1078},
    "Dieppe": {"lat": 49.9230, "lon": 1.0770},
    "Cherbourg": {"lat": 49.6500, "lon": -1.6200},
    
    "--- BRETAGNE ---": None,
    "Saint-Malo": {"lat": 48.6481, "lon": -2.0075},
    "Brest": {"lat": 48.3904, "lon": -4.4861},
    "Roscoff": {"lat": 48.7167, "lon": -3.9833},
    "Lorient": {"lat": 47.7483, "lon": -3.3700},
    "Vannes": {"lat": 47.6580, "lon": -2.7600},
    
    "--- ATLANTIQUE SUD ---": None,
    "La Rochelle": {"lat": 46.1603, "lon": -1.1511},
    "Les Sables-d'Olonne": {"lat": 46.4950, "lon": -1.7850},
    "Arcachon": {"lat": 44.6600, "lon": -1.1600},
    "Biarritz": {"lat": 43.4832, "lon": -1.5586},
    "Saint-Jean-de-Luz": {"lat": 43.3892, "lon": -1.6669},

    "--- MÉDITERRANÉE ---": None,
    "Marseille": {"lat": 43.2965, "lon": 5.3698},
    "Nice": {"lat": 43.7102, "lon": 7.2620},
    "Ajaccio": {"lat": 41.9213, "lon": 8.7360},
}

# Définition du fuseau horaire pour la France (gère l'heure d'été/hiver)
PARIS_TZ = pytz.timezone('Europe/Paris')

# --- FONCTIONS ---

def get_worldtides_data(lat, lon, start_date, end_date, api_key):
    """
    Récupère les marées via l'API WorldTides (stable et rapide).
    La requête de coefficient est retirée pour améliorer la stabilité.
    """
    if not api_key:
        return []

    start_dt = datetime.combine(start_date, datetime.min.time())
    start_ts = int(start_dt.timestamp())
    days = (end_date - start_date).days + 1
    
    # URL de base pour les extrêmes (marées hautes/basses)
    url_extremes = "https://www.worldtides.info/api/v3"
    params_extremes = {
        "extremes": "",
        "lat": lat,
        "lon": lon,
        "start": start_ts,
        "days": days,
        "key": api_key,
        "datum": "LAT",
        "timezone": "UTC"
    }
    
    # --- LA REQUÊTE POUR LES COEFFICIENTS A ÉTÉ RETIRÉE ICI ---
    
    try:
        # 1. Requête pour les extrêmes (Heure, Type, Hauteur)
        response_extremes = requests.get(url_extremes, params=params_extremes)
        response_extremes.raise_for_status()
        data_extremes = response_extremes.json()
        
        if 'error' in data_extremes:
            st.error(f"Erreur API (Extrêmes) : {data_extremes['error']}. Vérifiez votre clé ou votre quota.")
            return []

        processed_tides = []
        
        # Récupération des données d'extrêmes
        extremes_data = data_extremes.get('extremes', {}).get('heights') or data_extremes.get('extremes', [])
        
        if not extremes_data:
            return [] 

        for t in extremes_data:
            dt_utc = datetime.fromtimestamp(t['dt'], tz=timezone.utc)
            
            # Conversion en heure locale de Paris (gère l'heure d'été/hiver grâce à pytz)
            dt_local = dt_utc.astimezone(PARIS_TZ)
            
            tide_type = "Pleine Mer" if t['type'] == "High" else "Basse Mer"
            
            # Les coefficients ne sont plus récupérés
            
            processed_tides.append({
                "Date": dt_local.strftime("%Y-%m-%d"),
                "Heure": dt_local.strftime("%H:%M"),
                "Type": tide_type,
                "Hauteur (m)": round(t['height'], 2),
                "timestamp_obj": dt_local 
            })
                
        return processed_tides

    except Exception as e:
        # Erreur générale, souvent due à une mauvaise connexion ou timeout
        st.error(f"Erreur de connexion : {e}. Le problème peut venir de la limite des 100 tokens, d'une erreur réseau, ou d'une clé API invalide/expirée.")
        return []

def generate_ics(tides_data, location_name):
    c = Calendar()
    for tide in tides_data:
        e = Event()
        
        # Construction du titre simple : Pleine Mer - 4.50m (Coefficient retiré)
        title = f"{tide['Type']} - {tide['Hauteur (m)']:.2f}m"
        
        e.name = title
        e.begin = tide['timestamp_obj']
        e.duration = timedelta(minutes=30)
        e.location = location_name
        
        # Description détaillée (avec toutes les informations disponibles)
        e.description = (
            f"Lieu: {location_name}\n"
            f"Date: {tide['Date']}\n"
            f"Heure: {tide['Heure']} ({PARIS_TZ.zone})\n"
            f"Type de marée: {tide['Type']}\n"
            f"Hauteur: {tide['Hauteur (m)']:.2f}m\n"
            f"Source: WorldTides API"
        )
        
        c.events.add(e)
    return str(c)

# --- UI ---

st.title("✅ Calendrier Marées (Stable API)")
st.markdown("Ceci est la version la plus stable pour Streamlit Cloud. La clé API est lue depuis `st.secrets`.")

# Suppression du champ de saisie de la clé dans la barre latérale

with st.sidebar:
    st.header("1. Clé API")
    if API_KEY:
        st.success("Clé API WORLDTIDES_KEY chargée.")
    else:
        # Affiche le message d'erreur si la clé n'est pas trouvée (bloc try/except en haut)
        pass 
    
    st.header("2. Lieu")
    port_list = list(PORTS_DB.keys())
    selected_item = st.selectbox("Choisir un lieu", port_list)
    
    st.header("3. Dates")
    today = datetime.now().date()
    dates = st.date_input(
        "Sélectionnez l'intervalle",
        (today, today + timedelta(days=7)),
        format="DD/MM/YYYY",
        # Permet de choisir les mois et années facilement (comportement natif)
        help="Cliquez sur l'année ou le mois pour naviguer rapidement."
    )

# LOGIQUE PRINCIPALE
if selected_item and PORTS_DB[selected_item] is None:
    st.warning("Veuillez sélectionner une ville (pas un séparateur).")

elif st.button("Générer l'Agenda", type="primary"):
    if not API_KEY:
        # L'erreur a déjà été affichée en haut, on bloque juste l'exécution
        st.error("🛑 Impossible de lancer la requête : Clé API non trouvée.")
    elif len(dates) != 2:
        st.error("Sélectionnez une date de début et de fin.")
    else:
        start_date, end_date = dates
        
        if (end_date - start_date).days > 30:
            st.warning("Pour les tests et le quota gratuit, demandez moins de 30 jours à la fois.")

        coords = PORTS_DB[selected_item]
        
        with st.spinner("Interrogation de l'API WorldTides..."):
            # Appel API
            data = get_worldtides_data(
                coords['lat'], 
                coords['lon'], 
                start_date, 
                end_date, 
                API_KEY # Utilisation de la variable globale API_KEY lue par st.secrets
            )
        
        if data:
            st.success(f"{len(data)} marées trouvées pour {selected_item} !")
            
            # --- APERÇU ---
            df = pd.DataFrame(data)
            # Retrait de "Coeff" de l'affichage
            display_df = df[["Date", "Heure", "Type", "Hauteur (m)"]]
            
            st.subheader("📋 Aperçu des résultats")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # --- TÉLÉCHARGEMENT ---
            ics_content = generate_ics(data, selected_item)
            
            st.download_button(
                label="📥 Télécharger .ics",
                data=ics_content,
                file_name=f"maree_{selected_item}_{start_date}_{end_date}.ics",
                mime="text/calendar"
            )
            
        else:
            # L'erreur spécifique a déjà été affichée par la fonction get_worldtides_data
            pass
