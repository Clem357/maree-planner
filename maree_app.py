import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from ics import Calendar, Event
import pandas as pd
import time

# --- CONFIGURATION DES PORTS (IDs maree.info) ---
# Liste élargie aux villes majeures
PORTS = {
    "--- MANCHE / NORD ---": None,
    "Dunkerque": "2",
    "Calais": "4",
    "Boulogne-sur-Mer": "8",
    "Dieppe": "14",
    "Fécamp": "16",
    "Le Havre": "18",
    "Honfleur": "20",
    "Ouistreham": "24",
    "Cherbourg": "12",
    "Granville": "30",
    "Saint-Malo": "36",
    
    "--- BRETAGNE NORD/OUEST ---": None,
    "Perros-Guirec": "42",
    "Roscoff": "46",
    "Brest": "82",
    "Camaret": "84",
    "Douarnenez": "88",
    
    "--- BRETAGNE SUD ---": None,
    "Audierne": "90",
    "Concarneau": "96",
    "Lorient": "104",
    "Quiberon (Port Maria)": "110",
    "Vannes": "116",
    "Le Croisic": "118",
    "Saint-Nazaire": "119",
    
    "--- ATLANTIQUE ---": None,
    "Pornic": "120",
    "Noirmoutier": "122",
    "Les Sables-d'Olonne": "121",
    "La Rochelle": "125",
    "Rochefort": "128",
    "Royan": "132",
    "Arcachon": "136",
    "Cap Ferret": "135",
    "Bayonne / Boucau": "142",
    "Biarritz": "144",
    "Saint-Jean-de-Luz": "145",
    
    "--- MÉDITERRANÉE ---": None,
    "Port-Vendres": "156",
    "Sète": "160",
    "Marseille": "166",
    "Toulon": "168",
    "Nice": "174",
    "Ajaccio": "178",
    "Bastia": "180"
}

# --- FONCTION DE SCRAPING ---
def scrape_maree_info(port_id, start_date, end_date):
    """
    Récupère les marées jour par jour en lisant le HTML de maree.info
    """
    data_list = []
    
    # Calcul du nombre de jours
    delta = (end_date - start_date).days + 1
    
    # Barre de progression dans l'UI
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Headers pour simuler un vrai navigateur (évite certains blocages)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for i in range(delta):
        current_date = start_date + timedelta(days=i)
        
        # Mise à jour progression
        progress_val = (i + 1) / delta
        progress_bar.progress(progress_val)
        status_text.text(f"Lecture des données pour le {current_date.strftime('%d/%m/%Y')}...")
        
        # Construction URL : http://maree.info/{ID}?d=YYYYMMDD
        date_str = current_date.strftime("%Y%m%d")
        url = f"http://maree.info/{port_id}?d={date_str}"
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Le tableau principal a souvent l'ID 'MareeJours'
                table = soup.find('table', id='MareeJours')
                
                if table:
                    # On parcourt les lignes du tableau
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        # Une ligne de donnée valide a généralement au moins 3 cellules : Heure, Hauteur, Coeff
                        if len(cells) >= 2:
                            # 1. Heure
                            time_txt = cells[0].get_text(strip=True).replace('h', ':')
                            
                            # 2. Hauteur
                            height_txt = cells[1].get_text(strip=True)
                            
                            # 3. Coefficient (parfois vide)
                            coeff_txt = ""
                            if len(cells) > 2:
                                coeff_txt = cells[2].get_text(strip=True)
                            
                            # Nettoyage et Validation
                            if ':' in time_txt:
                                try:
                                    # Création objet date complet
                                    time_obj = datetime.strptime(time_txt, "%H:%M").time()
                                    full_dt = datetime.combine(current_date, time_obj)
                                    
                                    # Détection type (Simplifiée : on enregistre tout, l'utilisateur triera)
                                    # Sur maree.info, les pleines mers sont souvent en gras <b>, on peut tenter :
                                    is_bold = row.find('b') is not None
                                    tide_type = "Pleine Mer" if is_bold else "Basse Mer"
                                    # Si la détection gras échoue, on met générique
                                    if not is_bold and "MareeJours_" in str(row): 
                                        # Parfois le site utilise des classes CSS
                                        pass 

                                    data_list.append({
                                        "Date": current_date.strftime("%Y-%m-%d"),
                                        "Heure": time_txt,
                                        "Hauteur": height_txt,
                                        "Coeff": coeff_txt,
                                        "Type (Est.)": tide_type, 
                                        "datetime": full_dt # Pour l'ICS
                                    })
                                except ValueError:
                                    continue
            
            # Petite pause pour être poli avec le serveur
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Erreur pour {date_str}: {e}")
            continue

    status_text.empty()
    progress_bar.empty()
    return data_list

def generate_ics(tides_data, location_name):
    c = Calendar()
    for tide in tides_data:
        e = Event()
        
        # Construction du titre de l'événement
        # Modification demandée : coeff précisé explicitement dans le titre
        if tide['Coeff']:
            # Format avec Coefficient (ex: Pleine Mer - Coeff: 95 - 4.50m)
            title = f"{tide['Type (Est.)']} - Coeff: {tide['Coeff']} - {tide['Hauteur']}"
        else:
            # Format sans Coefficient (ex: Basse Mer - 1.20m)
            title = f"{tide['Type (Est.)']} - {tide['Hauteur']}"
        
        e.name = title
        e.begin = tide['datetime']
        e.duration = timedelta(minutes=30) # Durée arbitraire de l'événement
        e.location = location_name
        e.description = f"Heure : {tide['Heure']}\nHauteur : {tide['Hauteur']}\nCoefficient : {tide['Coeff']}\nSource: maree.info"
        
        c.events.add(e)
    return str(c)

# --- INTERFACE UTILISATEUR ---
st.set_page_config(page_title="Marées Scraping", page_icon="🦀")

st.title("🦀 Marées de France (Scraping)")
st.markdown("""
Générez votre calendrier des marées pour vos vacances.
*Source des données : maree.info*
""")

# Sidebar
with st.sidebar:
    st.header("1. Lieu")
    # Filtrer les séparateurs (None) pour la logique, mais garder dans la liste pour l'affichage
    display_ports = list(PORTS.keys())
    selected_port_name = st.selectbox("Choisir un port", display_ports)
    
    st.header("2. Dates")
    # Astuce UX : st.date_input permet de naviguer par année en cliquant sur l'année en haut du calendrier
    today = datetime.now()
    dates = st.date_input(
        "Période du séjour",
        (today, today + timedelta(days=7)),
        format="DD/MM/YYYY",
        help="Cliquez sur le mois ou l'année en haut du calendrier pour changer rapidement."
    )

# Corps principal
if PORTS[selected_port_name] is None:
    st.warning("Veuillez sélectionner une ville dans la liste (pas une région).")

elif st.button("Lancer la récupération (Scraping)"):
    if len(dates) != 2:
        st.error("Il faut une date de début et de fin.")
    else:
        start, end = dates
        
        # Vérification sécurité anti-abus
        if (end - start).days > 60:
            st.error("⚠️ Pour éviter de bloquer le site, veuillez demander moins de 60 jours à la fois.")
        else:
            st.info(f"Connexion à maree.info pour récupérer les données de **{selected_port_name}**...")
            
            # Lancement du scraping
            port_id = PORTS[selected_port_name]
            results = scrape_maree_info(port_id, start, end)
            
            if results:
                st.success(f"Terminé ! {len(results)} horaires récupérés.")
                
                # Aperçu Tableau
                df = pd.DataFrame(results)
                # On cache la colonne datetime technique pour l'affichage
                st.dataframe(df.drop(columns=["datetime"]), use_container_width=True, hide_index=True)
                
                # Génération ICS
                ics_file = generate_ics(results, selected_port_name)
                
                st.download_button(
                    label="📥 Télécharger mon Calendrier (.ics)",
                    data=ics_file,
                    file_name=f"marees_{selected_port_name}_{start}_{end}.ics",
                    mime="text/calendar"
                )
            else:
                st.error("Aucune donnée trouvée. Le site a peut-être changé sa structure ou le port n'a pas de données pour cette date.")
