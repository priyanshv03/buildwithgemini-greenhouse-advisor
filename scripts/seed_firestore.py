# Copyright 2026 Google LLC
import logging
from google.cloud import firestore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HARDCODED GCP PROJECT ID
PROJECT_ID = "qwiklabs-gcp-01-bff06e314e48"

SEED_PLANTS = [
    {
        "plant_id": "monstera-deliciosa",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "light_requirement": "Bright, indirect light",
        "watering_frequency_days": 7,
        "is_pet_safe": False,
        "last_watered": "2026-09-28",
        "notes": "Thrives in warm, humid environment. Wipe leaves to keep them dust-free."
    },
    {
        "plant_id": "snake-plant",
        "name": "Snake Plant",
        "species": "Dracaena trifasciata",
        "light_requirement": "Low to bright indirect light",
        "watering_frequency_days": 14,
        "is_pet_safe": False,
        "last_watered": "2026-09-20",
        "notes": "Extremely low maintenance. Avoid overwatering."
    },
    {
        "plant_id": "peace-lily",
        "name": "Peace Lily",
        "species": "Spathiphyllum",
        "light_requirement": "Medium, indirect light",
        "watering_frequency_days": 5,
        "is_pet_safe": False,
        "last_watered": "2026-10-01",
        "notes": "Loves high humidity and droops when thirsty."
    },
    {
        "plant_id": "parlor-palm",
        "name": "Parlor Palm",
        "species": "Chamaedorea elegans",
        "light_requirement": "Low to medium indirect light",
        "watering_frequency_days": 7,
        "is_pet_safe": True,
        "last_watered": "2026-09-30",
        "notes": "Safe for cats and dogs. Compact palm that prefers gentle moisture."
    },
    {
        "plant_id": "calathea-orbifolia",
        "name": "Calathea Orbifolia",
        "species": "Goeppertia orbifolia",
        "light_requirement": "Medium indirect light",
        "watering_frequency_days": 4,
        "is_pet_safe": True,
        "last_watered": "2026-10-01",
        "notes": "Pet safe, requires distilled or filtered water to avoid leaf tip burn."
    }
]

def seed_database():
    logger.info(f"Initializing Firestore client for project: {PROJECT_ID}")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("plants")

    for plant in SEED_PLANTS:
        doc_ref = collection_ref.document(plant["plant_id"])
        doc_ref.set(plant)
        logger.info(f"Seeded plant: {plant['name']} ({plant['plant_id']})")

    logger.info("Firestore database seeding completed successfully.")

if __name__ == "__main__":
    seed_database()
