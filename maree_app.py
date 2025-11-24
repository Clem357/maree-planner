import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from ics import Calendar, Event
import pytz # Pour la gestion des fuseaux horaires

# --- CONFIGURATION ---
st.set_page_config(page_title="Agenda Marées V2", page_icon="🌊", layout="centered")

# Clé API par défaut (laisser vide pour forcer l'utilisateur à la mettre)
DEFAULT_API_KEY = "" 

# Base de données des lieux (Lat/Lon)
PORTS_DB = {
    "--- BRETAGNE ---": None,
    "Saint-Malo": {"lat": 48.6481, "lon": -2.0075},
    "Brest":      {"lat": 48.3904, "lon": -4.4861},
    "Roscoff":    {"lat": 48.7167, "lon": -3.9833},
    "Lorient":    {"lat": 47.7483, "lon": -3.3700},
    "--- ATLANTIQUE ---": None,
    "La Rochelle":{"lat": 46.1603, "lon": -1.1511},
    "Arcachon":   {"lat": 44.6600, "lon": -1.1600},
    "Biarritz":   {"lat": 43.4832, "lon": -1.5586},
    "--- MANCHE / NORD ---": None,
    "Le Havre":   {"lat": 49.4944, "lon": 0.1078},
    "Dieppe":     {"lat": 49.9230, "lon": 1.0770},
    "Calais":     {"lat": 50.9513, "lon": 1.8587},
    "--- MÉDITERRANÉE ---": None,
    "Marseille":  {"lat": 43.2965, "lon": 5.3698},
    "Nice":       {"lat": 43.7102, "lon": 7.2620},
    "--- OUTRE-MER (Test Timezone) ---": None,
    "Pointe-à-Pitre (Guadeloupe)": {"lat": 16.2333, "lon": -61.5167},
}

# --- FONCTIONS ---

def get_worldtides_data(lat, lon, start_date, end_date, api_key, tz_name):
    """
    Récupère les marées via WorldTides et convertit dans le bon fuseau horaire.
    """
    # WorldTides attend un timestamp (Epoch)
    # On combine la date choisie avec minuit pour avoir le début de journée
    start_dt = datetime.combine(start_date, datetime.min.time())
    start_ts = int(start_dt.timestamp())
    
    # Calcul de la durée en jours
    days = (end_date - start_date).days + 1
    
    url = "https://www.worldtides.info/api/v3"
    params = {
        "extremes": "",       # On veut les pleines/basses mers
        "lat": lat,
        "lon": lon,
        "start": start_ts,
        "days": days,
        "key": api_key,
        "datum": "LAT"        # Lowest Astronomical Tide (référence cartes)
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            st.error(f"Erreur API : {data['error']}")
            return []

        processed_tides = []
        target_tz = pytz.timezone(tz_name)
        
        if 'extremes' in data:
            for t in data['extremes']:
                # 1. Lire le timestamp UTC fourni par l'API
                dt_utc = datetime.fromtimestamp(t['dt'], tz=timezone.utc)
                
                # 2. Convertir vers le fuseau horaire choisi par l'utilisateur
                dt_local = dt_utc.astimezone(target_tz)
                
                tide_type = "Pleine Mer" if t['type'] == "High" else "Basse Mer"
                
                processed_tides.append({
                    "Date": dt_local.strftime("%Y-%m-%d"),
                    "Heure": dt_local.strftime("%H:%M"),
                    "Type": tide_type,
                    "Hauteur (m)": round(t['height'], 2),
                    "timestamp_obj": dt_local # Gardé pour la création ICS
                })
                
        return processed_tides

    except Exception as e:
        st.error(f"Erreur de connexion ou clé invalide : {e}")
        return []

def create_ics_file(tides_data, location_name):
    c = Calendar()
    for tide in tides_data:
        e = Event()
        e.name = f"{tide['Type']} ({tide['Hauteur (m)']}m)"
        e.begin = tide['timestamp_obj']
        e.duration = timedelta(minutes=20)
        e.location = location_name
        e.description = f"Hauteur : {tide['Hauteur (m)']}m\nLieu : {location_name}"
        c.events.add(e)
    return str(c)

# --- INTERFACE ---

st.title("📅 Générateur de Marées pour Agenda")
st.markdown("Récupérez les horaires de marées et ajoutez-les à votre calendrier (Google/Apple/Outlook).")

with st.sidebar:
    st.header("1. Configuration")
    
    # Clé API
    api_key = st.text_input("Clé API WorldTides", value=DEFAULT_API_KEY, type="password", help="Inscrivez-vous sur worldtides.info pour avoir une clé gratuite.")
    
    # Sélection du port
    # On filtre les clés qui sont None (les séparateurs) pour la liste de choix
    valid_ports = [p for p in PORTS_DB.keys() if PORTS_DB[p] is not None]
    # On affiche tout dans la selectbox, mais on gérera la sélection
    selected_item = st.selectbox("Choisir un lieu", list(PORTS_DB.keys()))
    
    # Dates
    st.subheader("2. Dates du séjour")
    today = datetime.now()
    dates = st.date_input(
        "Sélectionnez l'intervalle",
        (today, today + timedelta(days=3)),
        format="DD/MM/YYYY"
    )
    
    # Fuseau Horaire
    st.subheader("3. Fuseau Horaire")
    # Liste des timezones courantes
    common_timezones = ['Europe/Paris', 'Atlantic/Canary', 'America/Guadeloupe', 'Indian/Reunion', 'Pacific/Noumea']
    all_timezones = pytz.all_timezones
    
    # Par défaut Europe/Paris (index 0 de common_timezones si on le met en premier)
    selected_tz = st.selectbox("Fuseau horaire local", common_timezones + all_timezones, index=0)

# LOGIQUE PRINCIPALE
if selected_item and PORTS_DB[selected_item] is None:
    st.warning("Veuillez sélectionner une ville (pas un séparateur).")

elif st.button("Rechercher les marées 🔎", type="primary"):
    if not api_key:
        st.error("Il faut une clé API WorldTides pour continuer.")
    elif len(dates) != 2:
        st.error("Veuillez sélectionner une date de DEBUT et une date de FIN.")
    else:
        start_date, end_date = dates
        coords = PORTS_DB[selected_item]
        
        with st.spinner("Interrogation des données satellites..."):
            # Appel API
            data = get_worldtides_data(
                coords['lat'], 
                coords['lon'], 
                start_date, 
                end_date, 
                api_key, 
                selected_tz
            )
        
        if data:
            # --- APERÇU (PREVIEW) ---
            st.success(f"{len(data)} marées trouvées pour {selected_item} !")
            
            # Création d'un DataFrame pour l'affichage propre
            df = pd.DataFrame(data)
            # On retire la colonne technique 'timestamp_obj' pour l'affichage
            display_df = df[["Date", "Heure", "Type", "Hauteur (m)"]]
            
            st.subheader("📋 Aperçu des résultats")
            
            # Affichage en tableau interactif (l'utilisateur peut trier)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # --- TÉLÉCHARGEMENT ---
            ics_content = create_ics_file(data, selected_item)
            
            st.download_button(
                label="📥 Télécharger pour mon Agenda (.ics)",
                data=ics_content,
                file_name=f"marees_{selected_item}_{start_date}_{end_date}.ics",
                mime="text/calendar"
            )
            
        else:
            st.warning("Aucune donnée trouvée (vérifiez vos dates ou votre crédit API).")

# Petit footer explicatif
st.markdown("---")
st.caption("Données fournies par WorldTides API. Usage personnel uniquement.")

