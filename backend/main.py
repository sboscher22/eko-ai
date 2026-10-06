from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re

app = FastAPI()

# Autoriser le frontend à communiquer avec Eko
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


# =========================================================
# RECHERCHE ACTUALITÉS
# =========================================================

def rechercher_actualites(question):
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(question)}&hl=fr&gl=FR&ceid=FR:fr"
    )

    try:
        reponse = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        reponse.raise_for_status()

        root = ET.fromstring(reponse.content)

        resultats = []

        for item in root.findall(".//item")[:8]:
            titre = item.findtext("title", "")
            lien = item.findtext("link", "")
            date = item.findtext("pubDate", "")

            if titre:
                resultats.append(
                    f"- {titre}\n"
                    f"  Date : {date}\n"
                    f"  Source : {lien}"
                )

        if not resultats:
            return "Aucune actualité récente trouvée."

        return "\n\n".join(resultats)

    except Exception as erreur:
        print("Erreur recherche Internet :", erreur)
        return "Impossible d'accéder aux informations Internet."


# =========================================================
# MÉTÉO
# =========================================================

def rechercher_meteo(ville):

    try:
        # Recherche de la ville
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"

        geo = requests.get(
            geo_url,
            params={
                "name": ville,
                "count": 1,
                "language": "fr",
                "format": "json"
            },
            timeout=10
        )

        geo.raise_for_status()

        geo_data = geo.json()

        if not geo_data.get("results"):
            return None

        lieu = geo_data["results"][0]

        latitude = lieu["latitude"]
        longitude = lieu["longitude"]
        nom = lieu["name"]
        pays = lieu.get("country", "")

        # Récupération de la météo actuelle
        meteo_url = "https://api.open-meteo.com/v1/forecast"

        meteo = requests.get(
            meteo_url,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,"
                    "relative_humidity_2m,"
                    "apparent_temperature,"
                    "precipitation,"
                    "weather_code,"
                    "wind_speed_10m"
                ),
                "timezone": "auto"
            },
            timeout=10
        )

        meteo.raise_for_status()

        data = meteo.json()

        current = data["current"]

        return {
            "ville": nom,
            "pays": pays,
            "temperature": current["temperature_2m"],
            "ressentie": current["apparent_temperature"],
            "humidite": current["relative_humidity_2m"],
            "pluie": current["precipitation"],
            "vent": current["wind_speed_10m"],
            "code_meteo": current["weather_code"]
        }

    except Exception as erreur:
        print("Erreur météo :", erreur)
        return None


# =========================================================
# DÉTECTER LA VILLE DANS LA QUESTION
# =========================================================

def trouver_ville(question):

    texte = question.strip()

    # Exemples :
    # "météo à Paris"
    # "quel temps à Saint-Brieuc"
    # "quel temps fait il a Lyon"
    correspondance = re.search(
        r"\b(?:à|a|sur|pour)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\- ]+)",
        texte,
        re.IGNORECASE
    )

    if correspondance:
        ville = correspondance.group(1).strip()

        # On enlève ce qui suit certaines expressions
        ville = re.split(
            r"\b(?:dans|pour|demain|aujourd'hui|aujourd|ce soir|cette semaine)\b",
            ville,
            flags=re.IGNORECASE
        )[0].strip()

        if ville:
            return ville

    # Si aucune ville n'est trouvée
    return "Paris"


# =========================================================
# PAGE PRINCIPALE
# =========================================================

@app.get("/")
def home():
    return {
        "name": "Eko AI",
        "status": "online"
    }


# =========================================================
# CHAT
# =========================================================

@app.post("/chat")
def chat(data: ChatRequest):

    question = data.message.lower()

    # Détecter une demande météo
    mots_meteo = [
        "météo",
        "meteo",
        "temps",
        "température",
        "temperature",
        "pluie",
        "vent",
        "soleil"
    ]

    demande_meteo = any(mot in question for mot in mots_meteo)

    # Si l'utilisateur demande la météo
    if demande_meteo:

        # Pour commencer, on utilise Saint-Brieuc par défaut
        ville = "Saint-Brieuc"

        meteo = rechercher_meteo(ville)

        if not meteo:
            return {
                "response": f"Je n'ai pas réussi à trouver la météo pour {ville}."
            }

        prompt = f"""
Tu es Eko AI, un assistant intelligent qui répond en français.

L'utilisateur demande :
{data.message}

Voici les données météo actuelles récupérées sur Internet :

Ville : {meteo["ville"]}
Pays : {meteo["pays"]}
Température : {meteo["temperature"]} °C
Température ressentie : {meteo["ressentie"]} °C
Humidité : {meteo["humidite"]} %
Précipitations : {meteo["pluie"]} mm
Vent : {meteo["vent"]} km/h
Code météo : {meteo["code_meteo"]}

Réponds naturellement en français.

Explique clairement la météo actuelle.
Ne fabrique aucune information qui n'est pas présente dans les données.
"""

    # Sinon, rechercher les actualités
    else:

        informations = rechercher_actualites(data.message)

        prompt = f"""
Tu es Eko AI, un assistant intelligent qui répond en français.

L'utilisateur demande :
{data.message}

Voici des informations récentes récupérées sur Internet :

{informations}

Réponds à l'utilisateur de manière claire et naturelle.

Utilise les informations Internet lorsqu'elles sont pertinentes.

Si les informations ne permettent pas de répondre correctement,
dis-le honnêtement au lieu d'inventer.
"""

    # Envoyer les informations à Ollama
    try:

        reponse = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        reponse.raise_for_status()

        donnees = reponse.json()

        return {
            "response": donnees.get(
                "response",
                "Je n'ai pas réussi à générer une réponse."
            )
        }

    except Exception as erreur:

        print("Erreur Ollama :", erreur)

        return {
            "response": "Eko n'arrive pas à contacter Ollama."
        }