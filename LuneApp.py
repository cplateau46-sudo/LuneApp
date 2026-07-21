import math
import pandas as pd
import requests
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
    initial_sidebar_state="auto"
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
LATITUDE_DEFAUT = 43.6045   # Toulouse (utilisée si aucune ville saisie ou géocodage impossible)
LONGITUDE_DEFAUT = 1.4442
VILLE_DEFAUT = "Toulouse"
TZ_NAME = "Europe/Paris"
TZ_LOCAL = ZoneInfo(TZ_NAME)

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

ZODIAQUE_TROPICAL = [
    (0, "Bélier ♈"), (30, "Taureau ♉"), (60, "Gémeaux ♊"), (90, "Cancer ♋"),
    (120, "Lion ♌"), (150, "Vierge ♍"), (180, "Balance ♎"), (210, "Scorpion ♏"),
    (240, "Sagittaire ♐"), (270, "Capricorne ♑"), (300, "Verseau ♒"), (330, "Poissons ♓")
]

# Correspondances traditionnelles (astrologie occidentale classique)
CORRESPONDANCES_PLANETES = {
    "Saturne": {"couleur": "Noir, gris foncé", "metal": "Plomb", "intention": "Structure, limites, discipline, ancrage"},
    "Jupiter": {"couleur": "Bleu roi, violet", "metal": "Étain", "intention": "Expansion, abondance, protection"},
    "Mars":    {"couleur": "Rouge", "metal": "Fer", "intention": "Action, courage, rupture"},
    "Soleil":  {"couleur": "Or, jaune", "metal": "Or", "intention": "Vitalité, rayonnement, affirmation"},
    "Vénus":   {"couleur": "Vert, rose", "metal": "Cuivre", "intention": "Amour, harmonie, beauté"},
    "Mercure": {"couleur": "Orange, multicolore", "metal": "Mercure (vif-argent)", "intention": "Communication, échange, apprentissage"},
    "Lune":    {"couleur": "Blanc, argent", "metal": "Argent", "intention": "Intuition, réceptivité, émotion"},
}

INTENTIONS_PLANETES = {
    "Amour, harmonie, beauté": "Vénus",
    "Argent, abondance, expansion": "Jupiter",
    "Protection, ancrage, structure": "Saturne",
    "Action, courage, rupture": "Mars",
    "Communication, apprentissage": "Mercure",
    "Intuition, émotion, réceptivité": "Lune",
    "Vitalité, affirmation, rayonnement": "Soleil",
}

def formater_duree(td):
    total_seconds = int(td.total_seconds())
    minutes = total_seconds // 60
    secondes = total_seconds % 60
    return f"{minutes} min {secondes} s"

def formater_heure(dt):
    return dt.astimezone(TZ_LOCAL).strftime("%H:%M")

@st.cache_data(ttl=86400)
def geocoder_ville(nom_ville):
    """Convertit un nom de ville en coordonnées via Nominatim (OpenStreetMap).
    Retourne (latitude, longitude, nom_affiche, trouve: bool)."""
    if not nom_ville or not nom_ville.strip():
        return LATITUDE_DEFAUT, LONGITUDE_DEFAUT, VILLE_DEFAUT, False
    try:
        reponse = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": nom_ville.strip(), "format": "json", "limit": 1},
            headers={"User-Agent": "HeuresPlanetaires-App/1.0"},
            timeout=6
        )
        reponse.raise_for_status()
        resultats = reponse.json()
        if resultats:
            r = resultats[0]
            return float(r["lat"]), float(r["lon"]), r["display_name"], True
    except Exception:
        pass
    return LATITUDE_DEFAUT, LONGITUDE_DEFAUT, VILLE_DEFAUT, False

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

def prochaine_heure_planete(planete, depart_dt, jours_max=7):
    """Cherche la prochaine occurrence d'une planète régente à partir de
    `depart_dt`, en balayant jusqu'à `jours_max` jours si besoin.
    Retourne (heure_dict, date_du_jour) ou (None, None)."""
    for offset in range(jours_max):
        jour_test = depart_dt.date() + timedelta(days=offset)
        heures_test, *_ = calculer_heures_planetaires(jour_test)
        for h in heures_test:
            if h["planete"] == planete and h["debut"] >= depart_dt:
                return h, jour_test
    return None, None

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

def calculer_signe_tropical(corps_celeste, date_cible_dt):
    """Signe du zodiaque tropical (12 divisions de 30° depuis l'équinoxe),
    distinct de la constellation réelle IAU."""
    t_skyfield = ts.from_datetime(date_cible_dt)
    astrometric = earth.at(t_skyfield).observe(corps_celeste).apparent()
    _, lon, _ = astrometric.ecliptic_latlon(epoch='date')
    degre = lon.degrees % 360
    signe = ZODIAQUE_TROPICAL[0][1]
    for seuil, nom in ZODIAQUE_TROPICAL:
        if degre >= seuil:
            signe = nom
    return signe

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
st.title("Heures Planétaires et Lune")
st.caption("Position des astres dans le ciel réel. Donc les 7 planètes visibles.")

ville_saisie = st.sidebar.text_input("Ta ville", value=VILLE_DEFAUT)
lat_util, lon_util, nom_lieu_trouve, ville_trouvee = geocoder_ville(ville_saisie)
lieu = LocationInfo("Local", "France", TZ_NAME, lat_util, lon_util)

if ville_trouvee:
    st.sidebar.caption(f"Localisation : {nom_lieu_trouve}")
else:
    st.sidebar.caption(f"Ville introuvable, localisation par défaut : {VILLE_DEFAUT}")

date_defaut = date.today()
if "date" in st.query_params:
    try:
        date_defaut = datetime.strptime(st.query_params["date"], "%Y-%m-%d").date()
    except ValueError:
        pass

date_selectionnee = st.sidebar.date_input("Date", value=date_defaut)
st.query_params["date"] = date_selectionnee.strftime("%Y-%m-%d")
st.sidebar.caption(f"Lien partageable : ajoute `?date={date_selectionnee.strftime('%Y-%m-%d')}` à la fin de l'URL de l'app")

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
signe_lune = calculer_signe_tropical(moon, maintenant)
signe_soleil = calculer_signe_tropical(sun_obj, maintenant)

# --- Section : État astronomique de la Lune ---
titre_section("ÉTAT ASTRONOMIQUE DE LA LUNE")
ligne_info("Constellation réelle (IAU)", infos_lune["constellation"], "v-green")
ligne_info("Signe zodiacal tropical", signe_lune, "v-green")
ligne_info("Phase actuelle", infos_lune["phase_nom"], "v-cyan")
if prochaine_nl:
    ligne_info("Prochaine Nouvelle Lune", f"{prochaine_nl.strftime('%d/%m/%Y à %H:%M')}  —  en {const_nl}", "v-pink")
if prochaine_pl:
    ligne_info("Prochaine Pleine Lune", f"{prochaine_pl.strftime('%d/%m/%Y à %H:%M')}  —  en {const_pl}", "v-pink")

st.write("")

# --- Section : Éphémérides solaires ---
titre_section("ÉPHÉMÉRIDE SOLAIRE")
ligne_info(
    "Jour",
    f"{nom_jour}  |  Maître du jour : {planete_regente} {SYMBOLES_PLANETES[planete_regente]}"
    f"  |  {CORRESPONDANCES_PLANETES[planete_regente]['intention']}",
    "v-green"
)
ligne_info("Constellation réelle (IAU)", const_soleil, "v-green")
ligne_info("Signe zodiacal tropical", signe_soleil, "v-green")
ligne_info("Lever", formater_heure(lever), "v-yellow")
ligne_info("Coucher", formater_heure(coucher), "v-yellow")
ligne_info("Heure diurne", formater_duree(duree_jour), "v-cyan")
ligne_info("Heure nocturne", formater_duree(duree_nuit), "v-cyan")

st.write("")

# --- Section : Heures planétaires ---
titre_section(f"HEURES PLANÉTAIRES ({date_selectionnee.strftime('%d/%m/%Y')})")

heure_actuelle = heure_planetaire_courante(heures, maintenant)

if heure_actuelle:
    corr = CORRESPONDANCES_PLANETES[heure_actuelle["planete"]]
    ligne_info(
        f"Heure actuelle — {heure_actuelle['planete']} {SYMBOLES_PLANETES[heure_actuelle['planete']]}",
        f"couleur : {corr['couleur']}  |  métal : {corr['metal']}  |  intention : {corr['intention']}",
        "v-pink"
    )
else:
    ligne_info("Heure actuelle", "hors plage (date/heure hors du cycle jour-nuit calculé)", "v-yellow")

planete_filtre = st.selectbox("Prochaine heure de quelle planète ?", ["—"] + ORDRE_CHALDEEN)
if planete_filtre != "—":
    prochaine, jour_trouve = prochaine_heure_planete(planete_filtre, maintenant)
    if prochaine:
        attente = prochaine["debut"] - maintenant
        jours_att, reste = divmod(int(attente.total_seconds()), 86400)
        heures_att, reste = divmod(reste, 3600)
        minutes_att = reste // 60
        delai = (f"{jours_att}j " if jours_att else "") + f"{heures_att}h{minutes_att:02d}"
        ligne_info(
            f"Prochaine heure de {planete_filtre} {SYMBOLES_PLANETES[planete_filtre]}",
            f"{jour_trouve.strftime('%d/%m')} — {formater_heure(prochaine['debut'])} - {formater_heure(prochaine['fin'])}"
            f"  ({prochaine['type']}, dans {delai})",
            "v-pink"
        )
    else:
        ligne_info(f"Prochaine heure de {planete_filtre}", "aucune dans les 7 prochains jours", "v-yellow")

intention_filtre = st.selectbox("Ou : je cherche une heure pour...", ["—"] + list(INTENTIONS_PLANETES.keys()))
if intention_filtre != "—":
    planete_associee = INTENTIONS_PLANETES[intention_filtre]
    prochaine, jour_trouve = prochaine_heure_planete(planete_associee, maintenant)
    if prochaine:
        attente = prochaine["debut"] - maintenant
        jours_att, reste = divmod(int(attente.total_seconds()), 86400)
        heures_att, reste = divmod(reste, 3600)
        minutes_att = reste // 60
        delai = (f"{jours_att}j " if jours_att else "") + f"{heures_att}h{minutes_att:02d}"
        ligne_info(
            f"Pour {intention_filtre.lower()} — {planete_associee} {SYMBOLES_PLANETES[planete_associee]}",
            f"{jour_trouve.strftime('%d/%m')} — {formater_heure(prochaine['debut'])} - {formater_heure(prochaine['fin'])}"
            f"  ({prochaine['type']}, dans {delai})",
            "v-pink"
        )
    else:
        ligne_info(f"Pour {intention_filtre.lower()}", "aucune heure adaptée dans les 7 prochains jours", "v-yellow")

with st.expander("C'est quoi une heure planétaire ?"):
    st.markdown(
        "Le jour et la nuit sont chacun divisés en 12 heures planétaires, dont la durée "
        "varie selon la saison (plus longues le jour en été, plus longues la nuit en hiver). "
        "Chaque heure est régie par une planète différente, selon un ordre fixe qui tourne "
        "en continu depuis l'Antiquité (l'ordre chaldéen). La première heure du jour porte "
        "toujours la planète qui gouverne le jour de la semaine — d'où \"lundi\" pour Lune, "
        "\"mardi\" pour Mars, etc. Se caler sur l'heure d'une planète, c'est agir en phase "
        "avec la qualité qu'elle représente plutôt qu'à contre-courant."
    )

st.write("")

def construire_dataframe(heures_liste, heure_active):
    return pd.DataFrame([{
        "N°": h["numero"],
        "Plage Horaire": f"{formater_heure(h['debut'])} - {formater_heure(h['fin'])}",
        "Régent Planétaire": f"{SYMBOLES_PLANETES[h['planete']]}  {h['planete']}",
        "Actuel": "Oui" if h is heure_active else ""
    } for h in heures_liste])

def styliser(heures_liste, heure_active):
    mask = pd.Series([h is heure_active for h in heures_liste])
    def style_ligne(row):
        if mask[row.name]:
            return ["background-color: #d8dce6; color: #1a2238; font-weight: 700"] * len(row)
        return [""] * len(row)
    return style_ligne

heures_jour = [h for h in heures if h["type"] == "Diurne"]
heures_nuit = [h for h in heures if h["type"] == "Nocturne"]

col_jour, col_nuit = st.columns(2)

with col_jour:
    st.markdown('<div class="info-row"><b>Diurnes</b></div>', unsafe_allow_html=True)
    df_jour = construire_dataframe(heures_jour, heure_actuelle)
    st.dataframe(
        df_jour.style.apply(styliser(heures_jour, heure_actuelle), axis=1),
        hide_index=True,
        width='stretch',
        height=(len(df_jour) + 1) * 35 + 3
    )

with col_nuit:
    st.markdown('<div class="info-row"><b>Nocturnes</b></div>', unsafe_allow_html=True)
    df_nuit = construire_dataframe(heures_nuit, heure_actuelle)
    st.dataframe(
        df_nuit.style.apply(styliser(heures_nuit, heure_actuelle), axis=1),
        hide_index=True,
        width='stretch',
        height=(len(df_nuit) + 1) * 35 + 3
    )

st.write("")

# --- Section : texte prêt à partager ---
titre_section("TEXTE PRÊT À PARTAGER")

if heure_actuelle:
    corr_actuelle = CORRESPONDANCES_PLANETES[heure_actuelle["planete"]]
    ligne_heure = (
        f"Heure planétaire en cours : {heure_actuelle['planete']} "
        f"({formater_heure(heure_actuelle['debut'])}-{formater_heure(heure_actuelle['fin'])})\n"
        f"Intention : {corr_actuelle['intention']}"
    )
else:
    ligne_heure = "Heure planétaire en cours : hors plage calculée"

texte_partage = (
    f"{nom_jour} {date_selectionnee.strftime('%d/%m/%Y')} — Maître du jour : {planete_regente}"
    f" ({CORRESPONDANCES_PLANETES[planete_regente]['intention']})\n\n"
    f"{ligne_heure}\n\n"
    f"Lune en {infos_lune['constellation']} ({signe_lune}) — {infos_lune['phase_nom']}\n"
    f"Soleil en {const_soleil} ({signe_soleil})"
)

st.code(texte_partage, language=None)
st.caption("Clique sur l'icône en haut à droite du bloc pour copier le texte.")
