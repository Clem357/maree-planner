import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from ics import Calendar, Event

# --- CONFIGURATION & DONNÉES ---
st.set_page_config(page_title="Calendrier Marées (Stable)", page_icon="🌊", layout="centered")

# Clé API par défaut (laisser vide pour obliger l'utilisateur à la mettre)
DEFAULT_API_KEY = st.secrets["WORLTIDES_KEY"]

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

# --- FONCTIONS ---

def get_worldtides_data(lat, lon, start_date, end_date, api_key):
    """
    Récupère les marées via l'API WorldTides (stable et rapide).
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    start_ts = int(start_dt.timestamp())
    days = (end_date - start_date).days + 1
    
    url = "https://www.worldtides.info/api/v3"
    params = {
        "extremes": "",
        "lat": lat,
        "lon": lon,
        "start": start_ts,
        "days": days,
        "key": api_key,
        "datum": "LAT",
        "timezone": "UTC" # On demande l'heure UTC, on convertira en heure locale française après
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'error' in data:
            st.error(f"Erreur API : {data['error']}. Vérifiez votre clé ou votre quota.")
            return []

        processed_tides = []
        
        if 'extremes' in data and 'heights' in data['extremes']:
             # WorldTides donne les extrêmes dans un sous-tableau heights
            extremes_data = data['extremes']['heights']
        elif 'extremes' in data:
            # Pour certains ports, l'ancienne structure sans 'heights' peut être utilisée.
            extremes_data = data['extremes']
        else:
            return [] # Aucune donnée

        # Récupération des coefficients (disponibles uniquement dans le champ 'prediction')
        # On va tenter de récupérer la prédiction complète pour les coefficients
        url_full = "https://www.worldtides.info/api/v3"
        params_full = {
            "property": "Coefficient", # Demande uniquement le coefficient
            "lat": lat,
            "lon": lon,
            "start": start_ts,
            "days": days,
            "key": api_key,
        }
        coeff_data = requests.get(url_full, params=params_full).json()
        coeff_map = {int(p['dt']): p['value'] for p in coeff_data.get('predictions', [])}

        
        for t in extremes_data:
            dt_utc = datetime.fromtimestamp(t['dt'], tz=timezone.utc)
            
            # Conversion simple en heure de Paris (UTC+1 ou UTC+2)
            # Pour un usage en France métropolitaine, c'est suffisant pour le calendrier.
            dt_local = dt_utc.astimezone(timezone(timedelta(hours=1)))
            
            tide_type = "Pleine Mer" if t['type'] == "High" else "Basse Mer"
            
            # Récupération du coefficient basé sur le timestamp
            coeff = coeff_map.get(t['dt'])
            
            processed_tides.append({
                "Date": dt_local.strftime("%Y-%m-%d"),
                "Heure": dt_local.strftime("%H:%M"),
                "Type": tide_type,
                "Hauteur (m)": round(t['height'], 2),
                "Coeff": int(round(coeff)) if coeff else '', # Arrondi du coefficient
                "timestamp_obj": dt_local 
            })
                
        return processed_tides

    except Exception as e:
        st.error(f"Erreur de connexion ou clé API invalide : {e}. Le problème peut venir de la limite des 100 tokens.")
        return []

def generate_ics(tides_data, location_name):
    c = Calendar()
    for tide in tides_data:
        e = Event()
        
        # Construction du titre : Pleine Mer - Coeff: 95 - 4.50m
        coeff_part = f" - Coeff: {tide['Coeff']}" if tide['Coeff'] else ""
        title = f"{tide['Type']}{coeff_part} - {tide['Hauteur (m)']:.2f}m"
        
        e.name = title
        e.begin = tide['timestamp_obj']
        e.duration = timedelta(minutes=30)
        e.location = location_name
        e.description = f"Type: {tide['Type']}\nHauteur: {tide['Hauteur (m)']:.2f}m\nCoefficient: {tide['Coeff']}\nSource: WorldTides API"
        
        c.events.add(e)
    return str(c)

# --- UI ---

st.title("✅ Calendrier Marées (Stable API)")
st.markdown("Ceci est la version la plus stable pour Streamlit Cloud. **Une clé API WorldTides est nécessaire.**")

with st.sidebar:
    st.header("1. Clé API")
    # Obliger l'utilisateur à fournir la clé
    user_api_key = st.text_input("Clé API WorldTides", type="password", help="100 requêtes gratuites par mois sur worldtides.info")
    
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
    if not user_api_key:
        st.error("🛑 Veuillez entrer votre clé API WorldTides pour que l'application puisse interroger les données.")
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
                user_api_key
            )
        
        if data:
            st.success(f"{len(data)} marées trouvées pour {selected_item} !")
            
            # --- APERÇU ---
            df = pd.DataFrame(data)
            display_df = df[["Date", "Heure", "Type", "Hauteur (m)", "Coeff"]]
            
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
            st.error("Aucune donnée trouvée (vérifiez la validité de votre clé API et votre quota mensuel gratuit).")
