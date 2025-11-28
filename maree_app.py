import streamlit as st
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from ics import Calendar, Event
import pandas as pd
import time
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Calendrier Marées V3", page_icon="🌊")

# Mapping : Nom Affiché -> Slug URL sur horaire-maree.fr
# Le slug est la partie de l'URL après /maree/ (ex: http://www.horaire-maree.fr/maree/Saint-Malo/)
PORTS = {
    "--- MANCHE EST ---": None,
    "Dunkerque": "Dunkerque",
    "Calais": "Calais",
    "Boulogne-sur-Mer": "Boulogne-sur-Mer",
    "Le Touquet": "Le-Touquet-Paris-Plage",
    "Dieppe": "Dieppe",
    "Fécamp": "Fecamp",
    "Le Havre": "Le-Havre",
    "Honfleur": "Honfleur",
    "Deauville / Trouville": "Trouville-sur-Mer",
    "Ouistreham": "Ouistreham",
    
    "--- MANCHE OUEST ---": None,
    "Cherbourg": "Cherbourg",
    "Granville": "Granville",
    "Saint-Malo": "Saint-Malo",
    "Dinard": "Dinard",
    "Erquy": "Erquy",
    "Paimpol": "Paimpol",
    "Perros-Guirec": "Perros-Guirec",
    "Roscoff": "Roscoff",
    
    "--- ATLANTIQUE BRETAGNE ---": None,
    "Brest": "Brest",
    "Camaret-sur-Mer": "Camaret-sur-Mer",
    "Douarnenez": "Douarnenez",
    "Audierne": "Audierne",
    "Concarneau": "Concarneau",
    "Lorient": "Lorient",
    "Quiberon": "Quiberon",
    "Vannes": "Vannes",
    
    "--- ATLANTIQUE SUD ---": None,
    "Le Croisic": "Le-Croisic",
    "Saint-Nazaire": "Saint-Nazaire",
    "Pornic": "Pornic",
    "Noirmoutier": "Noirmoutier-en-l-Ile",
    "Les Sables-d'Olonne": "Les-Sables-d-Olonne",
    "La Rochelle": "La-Rochelle",
    "Ile de Ré (Saint-Martin)": "Saint-Martin-de-Re",
    "Ile d'Oléron (Saint-Denis)": "Saint-Denis-d-Oleron",
    "Royan": "Royan",
    "Arcachon": "Arcachon",
    "Cap Ferret": "Le-Cap-Ferret",
    "Biarritz": "Biarritz",
    "Saint-Jean-de-Luz": "Saint-Jean-de-Luz",
    "Hendaye": "Hendaye",

    "--- MÉDITERRANÉE ---": None,
    "Marseille": "Marseille",
    "Toulon": "Toulon",
    "Nice": "Nice",
    "Sète": "Sete",
    "Port-Vendres": "Port-Vendres",
    "Ajaccio": "Ajaccio",
    "Bastia": "Bastia"
}

def clean_text(text):
    """Nettoie les textes HTML (enlève les espaces insécables, etc.)"""
    return text.replace('\xa0', '').strip()

def scrape_horaire_maree_fr(city_slug, start_date, end_date):
    """
    Scrape le site horaire-maree.fr
    Ce site affiche souvent toute l'année ou le mois en cours.
    On va récupérer la page et filtrer les dates.
    """
    data_list = []
    
    # User-Agent "Vrai navigateur" pour éviter le blocage
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    
    url = f"https://www.horaire-maree.fr/maree/{city_slug}/"
    
    try:
        # 1. Requête
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Lève une erreur si 404/500
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 2. Parsing
        # Le site utilise des tableaux avec la classe "tableau_maree" ou une structure par grille.
        # Structure courante : Une grille par jour ou un gros tableau.
        
        # On cherche le tableau des marées (souvent id="maree_jours" ou class="tableau_maree")
        # Sur horaire-maree.fr, c'est souvent un tableau général
        tables = soup.find_all('table')
        
        found_data = False
        
        for table in tables:
            # On cherche un tableau qui contient des dates
            rows = table.find_all('tr')
            current_parsing_date = None
            
            for row in rows:
                text_row = row.get_text(" ", strip=True)
                
                # --- A. DÉTECTION DE LA DATE ---
                # Les lignes de date ressemblent à "Dimanche 1 Janvier 2024"
                # On essaie de parser la date si on trouve un jour de la semaine
                days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
                
                # Vérifions si la ligne commence par un jour
                for d in days_fr:
                    if d in text_row:
                        # Nettoyage pour essayer de trouver la date
                        # Ex: "Mardi 23 Juillet 2024"
                        try:
                            # Regex pour extraire jour mois année
                            match = re.search(r'(\d{1,2})\s+([a-zA-Zéû]+)\s+(\d{4})', text_row)
                            if match:
                                day_num = match.group(1)
                                month_str = match.group(2).lower()
                                year_num = match.group(3)
                                
                                # Mapping mois FR -> Num
                                mois_map = {
                                    'janvier': 1, 'février': 2, 'fevrier': 2, 'mars': 3, 'avril': 4, 
                                    'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8, 'aout': 8, 
                                    'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12, 'decembre': 12
                                }
                                
                                if month_str in mois_map:
                                    current_parsing_date = datetime(int(year_num), mois_map[month_str], int(day_num)).date()
                        except:
                            pass
                        break # On a trouvé le jour, on passe à la suite de la ligne
                
                # --- B. DÉTECTION DES HEURES (Si on a une date valide) ---
                if current_parsing_date and start_date <= current_parsing_date <= end_date:
                    found_data = True
                    # Analyser les cellules : Heure | Hauteur | Coeff
                    # Sur ce site, c'est souvent : "Pleine mer" "04:12" "5.45m" "95"
                    cells = row.find_all('td')
                    
                    # Logique floue pour trouver les données dans la ligne
                    # On cherche un pattern HH:MM
                    
                    # On parcourt les cellules pour trouver des heures
                    row_content = [clean_text(c.get_text()) for c in cells]
                    
                    if len(row_content) >= 3:
                        # Est-ce une ligne de données ?
                        # Type (PM/BM) ?
                        tide_type = "?"
                        if "Pleine mer" in text_row or "Pleine Mer" in text_row:
                            tide_type = "Pleine Mer"
                        elif "Basse mer" in text_row or "Basse Mer" in text_row:
                            tide_type = "Basse Mer"
                        else:
                            continue # Pas une ligne de marée intéressante
                            
                        # Extraction Heure (Format XXhXX ou XX:XX)
                        time_val = None
                        height_val = ""
                        coeff_val = ""
                        
                        for cell in row_content:
                            # Chercher l'heure
                            if re.match(r'^\d{1,2}[:h]\d{2}$', cell):
                                time_val = cell.replace('h', ':')
                            # Chercher la hauteur (contient 'm')
                            elif 'm' in cell and re.search(r'\d', cell):
                                height_val = cell
                            # Chercher le coeff (nombre entier entre 20 et 120)
                            elif cell.isdigit() and 20 < int(cell) < 130:
                                coeff_val = cell
                        
                        if time_val:
                            full_dt = datetime.combine(current_parsing_date, datetime.strptime(time_val, "%H:%M").time())
                            
                            data_list.append({
                                "datetime": full_dt,
                                "Type": tide_type,
                                "Heure": time_val,
                                "Hauteur": height_val,
                                "Coeff": coeff_val
                            })
                            
        return data_list

    except Exception as e:
        st.error(f"Erreur de connexion au site : {e}")
        return []

def generate_ics(tides_data, location_name):
    c = Calendar()
    for tide in tides_data:
        e = Event()
        
        # Construction du titre
        # Ex: Pleine Mer - Coeff: 95 - 5.40m
        coeff_part = f" - Coeff: {tide['Coeff']}" if tide['Coeff'] else ""
        title = f"{tide['Type']}{coeff_part} - {tide['Hauteur']}"
        
        e.name = title
        e.begin = tide['datetime']
        e.duration = timedelta(minutes=30)
        e.location = location_name
        e.description = f"Type: {tide['Type']}\nHeure: {tide['Heure']}\nHauteur: {tide['Hauteur']}\nCoeff: {tide['Coeff']}\nSource: horaire-maree.fr"
        
        c.events.add(e)
    return str(c)

# --- UI ---

st.title("⚓ Calendrier Marées (Fiable)")
st.info("Source : horaire-maree.fr (Compatible coefficients & villes françaises)")

with st.sidebar:
    st.header("Lieu")
    # Liste filtrée
    port_list = list(PORTS.keys())
    selected_port_key = st.selectbox("Choisir une ville", port_list)
    
    st.header("Dates")
    today = datetime.now()
    dates = st.date_input(
        "Sélectionnez la période",
        (today, today + timedelta(days=7)),
        format="DD/MM/YYYY"
    )

if PORTS[selected_port_key] is None:
    st.warning("Choisissez une ville, pas une région.")
    
elif st.button("Récupérer les horaires"):
    if len(dates) != 2:
        st.error("Sélectionnez une date de début et de fin.")
    else:
        start, end = dates
        slug = PORTS[selected_port_key]
        
        with st.spinner(f"Récupération des données pour {selected_port_key}..."):
            # Appel Scraping
            results = scrape_horaire_maree_fr(slug, start, end)
            
            if results:
                st.success(f"{len(results)} marées trouvées !")
                
                # Affichage Tableau
                # On formate un peu pour que ce soit joli
                df = pd.DataFrame(results)
                display_df = df[["datetime", "Type", "Hauteur", "Coeff"]].copy()
                display_df["Date"] = display_df["datetime"].dt.strftime("%d/%m/%Y")
                display_df["Heure"] = display_df["datetime"].dt.strftime("%H:%M")
                display_df = display_df[["Date", "Heure", "Type", "Hauteur", "Coeff"]]
                
                st.table(display_df)
                
                # Génération ICS
                ics_data = generate_ics(results, selected_port_key)
                st.download_button(
                    label="📅 Télécharger pour Agenda (.ics)",
                    data=ics_data,
                    file_name=f"marees_{slug}.ics",
                    mime="text/calendar"
                )
            else:
                st.error("Aucune donnée trouvée. Vérifiez que la période n'est pas trop lointaine (le site affiche souvent max 1 an).")
