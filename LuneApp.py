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
    page_icon=None,
    layout="centered",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------
# THEME TERMINAL (CSS)
# ---------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');

.stApp {
    background-color: #fffff0;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}
.section-title {
    color: #1a2238;
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.5px;
    margin-top: 6px;
}
.section-line {
    border: none;
    border-top: 1px solid #c7c7b8;
    margin: 4px 0 14px 0;
}
.info-row {
    color: #2b2d3a;
    font-size: 0.95rem;
    margin: 3px 0;
    line-height: 1.5;
}
.branch { color: #9a9a8c; margin-right: 6px; }
.v-green { color: #2f4858; font-weight: 700; }
.v-pink  { color: #1a2238; font-weight: 700; }
.v-cyan  { color: #3d5a73; font-weight: 700; }
.v-yellow{ color: #52504a; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

def titre_section(titre):
    st.markdown(
        f'<div class="section-title">{titre}</div><hr class="section-line">',
        unsafe_allow_html=True
    )

def ligne_info(label, valeur, couleur="v-green"):
    st.markdown(
        f'<div class="info-row"><span class="branch">│</span>{label} : '
        f'<span class="{couleur}">{valeur}</span></div>',
        unsafe_allow_html=True
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
    "Psc": "Poissons ♓", "Cet": "Baleine", "Ori": "Orion"
}

def formater_duree(td):
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    secondes = total_seconds % 60
    return f"{minutes} min {secondes} s"

def formater_heure(dt):
    return dt.astimezone(TZ_LOCAL).strftime("%H:%M")

# ---------------------------------------------------------------
# CALCUL DES HEURES PLANÉTAIRES
# ---------------------------------------------------------------
def calculer_heures_planetaires(date_cible):
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
            "numero": i + 1, "type": "Diurne", "planete": planete,
            "debut": debut, "fin": fin, "duree": duree_jour
        })

    for i in range(12):
        planete = ORDRE_CHALDEEN[(index_depart + 12 + i) % 7]
        debut = coucher + duree_nuit * i
        fin = coucher + duree_nuit * (i + 1)
        heures.append({
            "numero": i + 1, "type": "Nocturne", "planete": planete,
            "debut": debut, "fin": fin, "duree": duree_nuit
        })

    return heures, nom_jour, planete_regente, lever, coucher, duree_jour, duree_nuit

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

def calculer_constellation_reelle(corps_celeste, date_cible_dt):
    """Constellation réelle IAU dans laquelle se trouve un corps céleste
    (Lune ou Soleil) à une date/heure donnée."""
    t_skyfield = ts.from_datetime(date_cible_dt)
    astrometric = earth.at(t_skyfield).observe(corps_celeste)
    code = constellation_at(astrometric)
    return NOMS_CONSTELLATIONS.get(code, code)

def calculer_infos_lunaires(date_cible_dt):
    t_skyfield = ts.from_datetime(date_cible_dt)

    const_lune = calculer_constellation_reelle(moon, date_cible_dt)

    angle_phase = almanac.moon_phase(eph, t_skyfield).degrees
    phase_nom = nom_phase_lunaire(angle_phase)
    illumination = (1 - math.cos(math.radians(angle_phase))) / 2 * 100

    return {
        "constellation": const_lune,
        "phase_angle": angle_phase,
        "phase_nom": phase_nom,
        "illumination": illumination
    }

def prochaines_phases_lunaires(date_cible_dt, jours_recherche=45):
    """Cherche la prochaine Nouvelle Lune (phase 0) et Pleine Lune (phase 2)
    dans les `jours_recherche` jours suivant la date donnée, avec la
    constellation réelle où se trouvera la Lune à ce moment-là."""
    t0 = ts.from_datetime(date_cible_dt)
    t1 = ts.from_datetime(date_cible_dt + timedelta(days=jours_recherche))
    times, phases = almanac.find_discrete(t0, t1, almanac.moon_phases(eph))

    prochaine_nl, prochaine_pl = None, None
    for t, phase in zip(times, phases):
        dt_phase = t.astimezone(TZ_LOCAL)
        if int(phase) == 0 and prochaine_nl is None:
            prochaine_nl = dt_phase
        if int(phase) == 2 and prochaine_pl is None:
            prochaine_pl = dt_phase
        if prochaine_nl and prochaine_pl:
            break

    const_nl = calculer_constellation_reelle(moon, prochaine_nl) if prochaine_nl else None
    const_pl = calculer_constellation_reelle(moon, prochaine_pl) if prochaine_pl else None

    return prochaine_nl, const_nl, prochaine_pl, const_pl

# ---------------------------------------------------------------
# INTERFACE STREAMLIT
# ---------------------------------------------------------------
st.title("Heures Planétaires & Lune")

date_selectionnee = st.sidebar.date_input("Date", value=date.today())
heure_selectionnee = st.sidebar.time_input("Heure", value=datetime.now(TZ_LOCAL).time())
utiliser_maintenant = st.sidebar.checkbox("Utiliser l'heure actuelle", value=True)

if utiliser_maintenant:
    maintenant = datetime.now(TZ_LOCAL)
else:
    maintenant = datetime.combine(date_selectionnee, heure_selectionnee, tzinfo=TZ_LOCAL)

heures, nom_jour, planete_regente, lever, coucher, duree_jour, duree_nuit = calculer_heures_planetaires(date_selectionnee)
infos_lune = calculer_infos_lunaires(maintenant)
prochaine_nl, const_nl, prochaine_pl, const_pl = prochaines_phases_lunaires(maintenant)
const_soleil = calculer_constellation_reelle(sun_obj, maintenant)

# --- Section : État astronomique de la Lune ---
titre_section("ÉTAT ASTRONOMIQUE DE LA LUNE")
ligne_info("Constellation réelle (IAU)", infos_lune["constellation"], "v-green")
ligne_info("Phase actuelle", infos_lune["phase_nom"], "v-cyan")
if prochaine_nl:
    ligne_info("Prochaine Nouvelle Lune", f"{prochaine_nl.strftime('%d/%m/%Y à %H:%M')}  —  en {const_nl}", "v-pink")
if prochaine_pl:
    ligne_info("Prochaine Pleine Lune", f"{prochaine_pl.strftime('%d/%m/%Y à %H:%M')}  —  en {const_pl}", "v-pink")

st.write("")

# --- Section : Éphémérides solaires ---
titre_section("ÉPHÉMÉRIDES SOLAIRES")
ligne_info("Jour", f"{nom_jour}  |  Maître du jour : {planete_regente} {SYMBOLES_PLANETES[planete_regente]}", "v-green")
ligne_info("Constellation réelle (IAU)", const_soleil, "v-green")
ligne_info("Lever", formater_heure(lever), "v-yellow")
ligne_info("Coucher", formater_heure(coucher), "v-yellow")
ligne_info("Heure diurne", formater_duree(duree_jour), "v-cyan")
ligne_info("Heure nocturne", formater_duree(duree_nuit), "v-cyan")

st.write("")

# --- Section : Heures planétaires ---
titre_section(f"HEURES PLANÉTAIRES ({date_selectionnee.strftime('%d/%m/%Y')})")

heure_actuelle = heure_planetaire_courante(heures, maintenant)

df = pd.DataFrame([{
    "N°": h["numero"],
    "Type": h["type"],
    "Plage Horaire": f"{formater_heure(h['debut'])} - {formater_heure(h['fin'])}",
    "Régent Planétaire": f"{SYMBOLES_PLANETES[h['planete']]}  {h['planete']}",
    "Actuel": "Oui" if h is heure_actuelle else ""
} for h in heures])

mask = pd.Series([h is heure_actuelle for h in heures])

def style_ligne(row):
    if mask[row.name]:
        return ["background-color: #eaeadb; color: #1a2238; font-weight: 700"] * len(row)
    return [""] * len(row)

st.dataframe(
    df.style.apply(style_ligne, axis=1),
    hide_index=True,
    width='stretch'
)
