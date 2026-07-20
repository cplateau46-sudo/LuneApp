import math
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from astral import LocationInfo
from astral.sun import sun

from skyfield.api import load, load_constellation_map
from skyfield import almanac

# ---------------------------------------------------------------
# CONFIG PAGE
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Calculateur d'Heures Planétaires & Lune",
    page_icon="🔮",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------
# RESSOURCES ASTRONOMIQUES (mise en cache)
# ---------------------------------------------------------------
@st.cache_resource
def charger_ressources_skyfield():
    ts = load.timescale()
    eph = load('de421.bsp')
    constellation_at = load_constellation_map()
    return ts, eph, constellation_at

ts, eph, constellation_at = charger_ressources_skyfield()
earth, moon, sun_obj = eph['earth'], eph['moon'], eph['sun']

# ---------------------------------------------------------------
# CONSTANTES & CONFIGURATION LOCALISATION
# ---------------------------------------------------------------
LATITUDE = 43.6045   # Toulouse / Lagardelle
LONGITUDE = 1.4442
TZ_NAME = "Europe/Paris"
TZ_LOCAL = ZoneInfo(TZ_NAME)

lieu = LocationInfo("Local", "France", TZ_NAME, LATITUDE, LONGITUDE)

ORDRE_CHALDEEN = ["Saturne", "Jupiter", "Mars", "Soleil", "Vénus", "Mercure", "Lune"]

REGENTS_JOURS = {
    0: ("Lune", "Lundi"),
    1: ("Mars", "Mardi"),
    2: ("Mercure", "Mercredi"),
    3: ("Jupiter", "Jeudi"),
    4: ("Vénus", "Vendredi"),
    5: ("Saturne", "Samedi"),
    6: ("Soleil", "Dimanche")
}

SYMBOLES_PLANETES = {
    "Saturne": "♄", "Jupiter": "♃", "Mars": "♂",
    "Soleil": "☉", "Vénus": "♀", "Mercure": "☿", "Lune": "☽"
}

NOMS_CONSTELLATIONS = {
    "Ari": "Bélier ♈", "Tau": "Taureau ♉", "Gem": "Gémeaux ♊",
    "Cnc": "Cancer ♋", "Leo": "Lion ♌", "Vir": "Vierge ♍",
    "Lib": "Balance ♎", "Sco": "Scorpion ♏", "Oph": "Serpentaire ⛎",
    "Sgr": "Sagittaire ♐", "Cap": "Capricorne ♑", "Aqr": "Verseau ♒",
    "Psc": "Poissons ♓", "Cet": "Baleine 🐳", "Ori": "Orion 🏹"
}

def formater_duree(td):
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    secondes = total_seconds % 60
    return f"{minutes} min {secondes} s"

def formater_heure(dt):
    return dt.astimezone(TZ_LOCAL).strftime("%H:%M:%S")

# ---------------------------------------------------------------
# CALCUL DES HEURES PLANÉTAIRES
# ---------------------------------------------------------------
def calculer_heures_planetaires(date_cible):
    """
    Découpe le jour (lever->coucher) et la nuit (coucher->lever du lendemain)
    en 12 heures planétaires chacun, selon l'ordre chaldéen, en partant
    de la planète régente du jour de la semaine.
    """
    s_jour = sun(lieu.observer, date=date_cible, tzinfo=TZ_LOCAL)
    s_lendemain = sun(lieu.observer, date=date_cible + timedelta(days=1), tzinfo=TZ_LOCAL)

    lever = s_jour["sunrise"]
    coucher = s_jour["sunset"]
    lever_lendemain = s_lendemain["sunrise"]

    duree_jour = (coucher - lever) / 12
    duree_nuit = (lever_lendemain - coucher) / 12

    jour_semaine = date_cible.weekday()
    planete_regente, nom_jour = REGENTS_JOURS[jour_semaine]
    index_depart = ORDRE_CHALDEEN.index(planete_regente)

    heures = []

    for i in range(12):
        planete = ORDRE_CHALDEEN[(index_depart + i) % 7]
        debut = lever + duree_jour * i
        fin = lever + duree_jour * (i + 1)
        heures.append({
            "numero": i + 1, "type": "Jour", "planete": planete,
            "debut": debut, "fin": fin, "duree": duree_jour
        })

    for i in range(12):
        planete = ORDRE_CHALDEEN[(index_depart + 12 + i) % 7]
        debut = coucher + duree_nuit * i
        fin = coucher + duree_nuit * (i + 1)
        heures.append({
            "numero": i + 1, "type": "Nuit", "planete": planete,
            "debut": debut, "fin": fin, "duree": duree_nuit
        })

    return heures, nom_jour, planete_regente, lever, coucher

def heure_planetaire_courante(heures, maintenant):
    for h in heures:
        if h["debut"] <= maintenant < h["fin"]:
            return h
    return None

# ---------------------------------------------------------------
# CALCUL DES INFOS LUNAIRES
# ---------------------------------------------------------------
def nom_phase_lunaire(angle_deg):
    if angle_deg < 45 or angle_deg >= 315:
        return "Nouvelle Lune"
    elif angle_deg < 90:
        return "Premier Croissant"
    elif angle_deg < 135:
        return "Premier Quartier"
    elif angle_deg < 180:
        return "Lune Gibbeuse Croissante"
    elif angle_deg < 225:
        return "Pleine Lune"
    elif angle_deg < 270:
        return "Lune Gibbeuse Décroissante"
    else:
        return "Dernier Quartier"

def calculer_infos_lunaires(date_cible_dt):
    t_skyfield = ts.from_datetime(date_cible_dt)

    astrometric = earth.at(t_skyfield).observe(moon)
    constellation_code = constellation_at(astrometric)
    const_traduite = NOMS_CONSTELLATIONS.get(constellation_code, constellation_code)

    angle_phase = almanac.moon_phase(eph, t_skyfield).degrees
    phase_nom = nom_phase_lunaire(angle_phase)
    illumination = (1 - math.cos(math.radians(angle_phase))) / 2 * 100

    return {
        "constellation": const_traduite,
        "phase_angle": angle_phase,
        "phase_nom": phase_nom,
        "illumination": illumination
    }

# ---------------------------------------------------------------
# INTERFACE STREAMLIT
# ---------------------------------------------------------------
st.title("🔮 Heures Planétaires & Lune")

date_selectionnee = st.sidebar.date_input("Date", value=date.today())
heure_selectionnee = st.sidebar.time_input("Heure", value=datetime.now(TZ_LOCAL).time())
utiliser_maintenant = st.sidebar.checkbox("Utiliser l'heure actuelle", value=True)

if utiliser_maintenant:
    maintenant = datetime.now(TZ_LOCAL)
else:
    maintenant = datetime.combine(date_selectionnee, heure_selectionnee, tzinfo=TZ_LOCAL)

heures, nom_jour, planete_regente, lever, coucher = calculer_heures_planetaires(date_selectionnee)

st.subheader(f"{nom_jour} — jour régi par {planete_regente} {SYMBOLES_PLANETES[planete_regente]}")
st.write(f"Lever du soleil : **{formater_heure(lever)}** — Coucher du soleil : **{formater_heure(coucher)}**")

heure_actuelle = heure_planetaire_courante(heures, maintenant)
if heure_actuelle:
    st.success(
        f"Heure planétaire en cours : **{heure_actuelle['planete']} "
        f"{SYMBOLES_PLANETES[heure_actuelle['planete']]}** "
        f"({heure_actuelle['type']} n°{heure_actuelle['numero']}, "
        f"jusqu'à {formater_heure(heure_actuelle['fin'])})"
    )
else:
    st.info("Aucune heure planétaire en cours pour cette date (date passée ou future).")

st.divider()
st.subheader("Tableau des 24 heures planétaires")

def construire_dataframe(heures_liste):
    return pd.DataFrame([{
        "N°": h["numero"],
        "Planète": f"{SYMBOLES_PLANETES[h['planete']]}  {h['planete']}",
        "Début": formater_heure(h["debut"]),
        "Fin": formater_heure(h["fin"]),
        "Durée": formater_duree(h["duree"]),
    } for h in heures_liste])

def surligner_heure_active(heures_liste, maintenant):
    mask = pd.Series([h["debut"] <= maintenant < h["fin"] for h in heures_liste])

    def style_ligne(row):
        if mask[row.name]:
            return ["background-color: #2e7d32; color: white; font-weight: bold"] * len(row)
        return [""] * len(row)

    return style_ligne

heures_jour = [h for h in heures if h["type"] == "Jour"]
heures_nuit = [h for h in heures if h["type"] == "Nuit"]

onglet_jour, onglet_nuit = st.tabs(["☀️ Heures de jour", "🌙 Heures de nuit"])

with onglet_jour:
    df_jour = construire_dataframe(heures_jour)
    style_jour = surligner_heure_active(heures_jour, maintenant)
    st.dataframe(
        df_jour.style.apply(style_jour, axis=1),
        hide_index=True,
        width='stretch'
    )

with onglet_nuit:
    df_nuit = construire_dataframe(heures_nuit)
    style_nuit = surligner_heure_active(heures_nuit, maintenant)
    st.dataframe(
        df_nuit.style.apply(style_nuit, axis=1),
        hide_index=True,
        width='stretch'
    )

st.divider()
st.subheader("🌙 Informations lunaires")

infos_lune = calculer_infos_lunaires(maintenant)
st.write(f"Constellation actuelle de la Lune : **{infos_lune['constellation']}**")
st.write(f"Phase actuelle : **{infos_lune['phase_nom']}** ({infos_lune['phase_angle']:.1f}°)")
st.write(f"Illumination : **{infos_lune['illumination']:.1f}%**")