# Copyright 2026 Google LLC
import datetime
import json
import os
import urllib.parse
import urllib.request
import uuid
from typing import Any

from google import genai
from google.adk.tools import ToolContext
from google.cloud import firestore, storage
from google.genai import types

# HARDCODED CONSTANTS (Required for Agent Platform & Cloud Storage compatibility)
PROJECT_ID = "qwiklabs-gcp-01-bff06e314e48"
BUCKET_NAME = "greenhouse-advisor-assets-qwiklabs-gcp-01-bff06e314e48"


def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client bound to the hardcoded GCP Project ID."""
    return firestore.Client(project=PROJECT_ID)


def list_greenhouse_plants() -> list[dict[str, Any]]:
    """Retrieves all plant items from the greenhouse catalog in Firestore.

    Returns:
        A list of plant objects containing care details, light needs, watering frequency, and pet safety info.
    """
    db = get_firestore_client()
    docs = db.collection("plants").stream()
    plants = []
    for doc in docs:
        data = doc.to_dict()
        plants.append(data)
    return plants


def get_plant_details(plant_id: str) -> dict[str, Any] | str:
    """Retrieves detailed care information for a specific plant by its plant ID.

    Args:
        plant_id: The unique identifier for the plant (e.g., 'monstera-deliciosa', 'snake-plant').

    Returns:
        A dictionary containing plant details or an error message if not found.
    """
    db = get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return f"Plant '{plant_id}' not found in the greenhouse catalog."


def add_or_update_plant(
    plant_id: str,
    name: str,
    species: str,
    light_requirement: str,
    watering_frequency_days: int,
    is_pet_safe: bool,
    notes: str = ""
) -> str:
    """Adds a new plant or updates an existing plant's information in the greenhouse catalog.

    Args:
        plant_id: Unique string identifier for the plant (e.g. 'pothos').
        name: Common name of the plant (e.g. 'Golden Pothos').
        species: Botanical species name (e.g. 'Epipremnum aureum').
        light_requirement: Ideal light conditions (e.g. 'Medium to bright indirect light').
        watering_frequency_days: Recommended interval between waterings in days.
        is_pet_safe: True if non-toxic to pets, False otherwise.
        notes: Additional care advice or notes.

    Returns:
        Confirmation string indicating successful update/add.
    """
    db = get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)

    existing_doc = doc_ref.get()
    last_watered = existing_doc.to_dict().get("last_watered") if existing_doc.exists else datetime.date.today().isoformat()

    plant_data = {
        "plant_id": plant_id,
        "name": name,
        "species": species,
        "light_requirement": light_requirement,
        "watering_frequency_days": watering_frequency_days,
        "is_pet_safe": is_pet_safe,
        "last_watered": last_watered,
        "notes": notes
    }
    doc_ref.set(plant_data, merge=True)
    return f"Successfully saved plant '{name}' ({plant_id}) to Firestore."


def log_watering_event(plant_id: str, date: str | None = None) -> str:
    """Logs a watering event for a specific plant, updating its 'last_watered' date.

    Args:
        plant_id: Unique string identifier for the plant.
        date: Optional date string in YYYY-MM-DD format. Defaults to today's date if omitted.

    Returns:
        Confirmation message with the updated watering date.
    """
    db = get_firestore_client()
    doc_ref = db.collection("plants").document(plant_id)
    doc = doc_ref.get()
    if not doc.exists:
        return f"Cannot log watering: Plant '{plant_id}' not found."

    if not date:
        date = datetime.date.today().isoformat()

    doc_ref.update({"last_watered": date})
    return f"Logged watering for plant '{plant_id}' on {date}."


def check_local_weather(location: str) -> dict[str, Any] | str:
    """Fetches live weather conditions (temperature in °F and relative humidity %) for a location.

    Args:
        location: City or location name (e.g., 'San Francisco', 'Austin', 'Seattle').

    Returns:
        A dictionary containing location, temperature_f, and humidity_percent.
    """
    try:
        encoded_loc = urllib.parse.quote(location)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
        with urllib.request.urlopen(req) as resp:
            geo_data = json.loads(resp.read().decode())

        results = geo_data.get("results", [])
        if not results:
            return f"Could not find coordinates for location: '{location}'."

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        city_name = results[0].get("name", location)

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m&temperature_unit=fahrenheit"
        w_req = urllib.request.Request(weather_url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
        with urllib.request.urlopen(w_req) as w_resp:
            weather_data = json.loads(w_resp.read().decode())

        current = weather_data.get("current", {})
        temp_f = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")

        return {
            "location": city_name,
            "temperature_f": temp_f,
            "humidity_percent": humidity,
            "status": "success"
        }
    except Exception as e:
        return f"Error fetching weather for {location}: {str(e)}"


def lookup_botanical_taxonomy(plant_name: str) -> dict[str, Any] | str:
    """Looks up official botanical taxonomy (scientific name, family, genus, and kingdom) for a plant.

    Uses the Global Biodiversity Information Facility (GBIF) public species database API.

    Args:
        plant_name: Common or scientific name of the plant (e.g., 'Monstera deliciosa', 'Spathiphyllum', 'Ficus').

    Returns:
        A dictionary containing scientific name, family, genus, and kingdom data.
    """
    api_key = os.getenv("TREFLE_API_KEY") or os.getenv("PERENUAL_API_KEY")
    if api_key:
        try:
            url = f"https://perenual.com/api/species-list?key={api_key}&q={urllib.parse.quote(plant_name)}"
            req = urllib.request.Request(url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                if data.get("data"):
                    first = data["data"][0]
                    return {
                        "common_name": first.get("common_name"),
                        "scientific_name": first.get("scientific_name"),
                        "source": "Perenual API (Authenticated)"
                    }
        except Exception:
            pass

    try:
        query_enc = urllib.parse.quote(plant_name)
        url = f"https://api.gbif.org/v1/species/match?name={query_enc}"
        req = urllib.request.Request(url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if data.get("matchType") != "NONE":
                return {
                    "query": plant_name,
                    "scientific_name": data.get("scientificName"),
                    "canonical_name": data.get("canonicalName"),
                    "genus": data.get("genus"),
                    "family": data.get("family"),
                    "kingdom": data.get("kingdom"),
                    "confidence": data.get("confidence"),
                    "source": "GBIF Species Taxonomy API"
                }

        s_url = f"https://api.gbif.org/v1/species/suggest?q={query_enc}&limit=1"
        s_req = urllib.request.Request(s_url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
        with urllib.request.urlopen(s_req) as s_resp:
            s_data = json.loads(s_resp.read().decode())
            if s_data:
                first = s_data[0]
                return {
                    "query": plant_name,
                    "scientific_name": first.get("scientificName"),
                    "canonical_name": first.get("canonicalName"),
                    "genus": first.get("genus"),
                    "family": first.get("family"),
                    "kingdom": first.get("kingdom"),
                    "source": "GBIF Species Taxonomy API"
                }

        return f"No botanical taxonomy match found for '{plant_name}'."
    except Exception as e:
        return f"Error looking up botanical taxonomy for '{plant_name}': {str(e)}"


def geocode_address(address: str) -> dict[str, Any] | str:
    """Converts a physical address into geographic coordinates (latitude and longitude).

    Uses the Google Maps Geocoding REST API. Reads API key from GOOGLE_MAPS_API_KEY environment variable.

    Args:
        address: The address or place string to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary containing formatted_address, location (latitude/longitude), and place_id.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in the environment."

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "GreenhouseAdvisor/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") == "OK" and data.get("results"):
            first = data["results"][0]
            loc = first.get("geometry", {}).get("location", {})
            return {
                "address": address,
                "formatted_address": first.get("formatted_address"),
                "location": {
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng")
                },
                "place_id": first.get("place_id")
            }
        return f"Geocoding failed for address '{address}': Status {data.get('status')}."
    except Exception as e:
        return f"Error during geocoding request: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "florist",
    radius_meters: float = 3000.0
) -> list[dict[str, Any]] | str:
    """Finds nearby places of a specified type (e.g. 'florist', 'garden_center', 'park') around coordinates.

    Uses Google Maps Places API (New) searchNearby REST endpoint. Reads key from GOOGLE_MAPS_API_KEY environment variable.

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g., 'florist', 'garden_center', 'park', 'store').
        radius_meters: Search radius in meters (default 3000m / 3km).

    Returns:
        A list of place dictionaries containing name, address, and location.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not configured in the environment."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius_meters
            }
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        places = []
        for item in data.get("places", []):
            places.append({
                "name": item.get("displayName", {}).get("text", "N/A"),
                "address": item.get("formattedAddress", "N/A"),
                "location": {
                    "latitude": item.get("location", {}).get("latitude"),
                    "longitude": item.get("location", {}).get("longitude")
                }
            })
        return places if places else f"No nearby places of type '{place_type}' found."
    except Exception as e:
        return f"Error querying Places API (New): {str(e)}"


async def generate_plant_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an AI image of a plant or greenhouse item using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as a session artifact for the Playground UI, uploads the image bytes directly
    to the public Cloud Storage bucket without local file writes, and returns its public HTTPS URL.

    Args:
        prompt: Detailed prompt describing the plant or greenhouse visual (e.g., 'A vibrant Monstera Deliciosa in a ceramic pot').
        tool_context: ADK ToolContext instance injected automatically for saving session artifacts.

    Returns:
        The public HTTPS URL of the uploaded image (https://storage.googleapis.com/<bucket>/<object>).
    """
    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            )
        )
    except Exception as e:
        return f"Error invoking gemini-3.1-flash-lite-image model: {str(e)}"

    image_bytes = None
    mime_type = "image/jpeg"
    for candidate in response.candidates:
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break
        if image_bytes:
            break

    if not image_bytes:
        return "Error: Image generation completed but no image bytes were returned."

    image_id = uuid.uuid4().hex[:8]
    ext = "png" if "png" in mime_type.lower() else "jpg"
    image_filename = f"plant_{image_id}.{ext}"

    # 1. Save as ADK session artifact for Playground UI
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    await tool_context.save_artifact(filename=image_filename, artifact=artifact_part)

    # 2. Upload image bytes directly to public GCS bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(image_filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{image_filename}"
    return public_url


async def generate_plant_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates an AI video of a plant or greenhouse item using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the generated video as a session artifact for the Playground UI, uploads the video bytes directly
    to the public Cloud Storage bucket without local file writes, and returns its public HTTPS URL.

    Args:
        prompt: Detailed prompt describing the video scene (e.g., 'A time-lapse of a greenhouse fern frond unfurling in sunlight').
        tool_context: ADK ToolContext instance injected automatically for saving session artifacts.

    Returns:
        The public HTTPS URL of the uploaded video (https://storage.googleapis.com/<bucket>/<object>).
    """
    import base64

    client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    try:
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )
    except Exception as e:
        return f"Error invoking gemini-omni-flash-preview model: {str(e)}"

    if (
        not hasattr(interaction, "output_video")
        or not interaction.output_video
        or not getattr(interaction.output_video, "data", None)
    ):
        return "Error: Video generation completed but no video data was returned."

    try:
        video_bytes = base64.b64decode(interaction.output_video.data)
    except Exception as e:
        return f"Error decoding generated video data: {str(e)}"

    video_id = uuid.uuid4().hex[:8]
    video_filename = f"plant_{video_id}.mp4"

    # 1. Save as ADK session artifact for Playground UI
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
    await tool_context.save_artifact(filename=video_filename, artifact=artifact_part)

    # 2. Upload video bytes directly to public GCS bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(video_filename)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{video_filename}"
    return public_url

