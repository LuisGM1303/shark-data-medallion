"""Seed species: demonstration inputs, NOT an access-control list.

The universe of species is open. These 18 species are used only to
demonstrate the pipeline reproducibly. Any new species can be processed
by providing its scientific name.
"""

SEED_SPECIES = [
    {"species_key": "carcharodon_carcharias",   "scientific_name": "Carcharodon carcharias",   "wikipedia_title": "Great white shark"},
    {"species_key": "rhincodon_typus",           "scientific_name": "Rhincodon typus",           "wikipedia_title": "Whale shark"},
    {"species_key": "cetorhinus_maximus",        "scientific_name": "Cetorhinus maximus",        "wikipedia_title": "Basking shark"},
    {"species_key": "galeocerdo_cuvier",         "scientific_name": "Galeocerdo cuvier",         "wikipedia_title": "Tiger shark"},
    {"species_key": "sphyrna_mokarran",          "scientific_name": "Sphyrna mokarran",          "wikipedia_title": "Great hammerhead"},
    {"species_key": "sphyrna_lewini",            "scientific_name": "Sphyrna lewini",            "wikipedia_title": "Scalloped hammerhead"},
    {"species_key": "prionace_glauca",           "scientific_name": "Prionace glauca",           "wikipedia_title": "Blue shark"},
    {"species_key": "isurus_oxyrinchus",         "scientific_name": "Isurus oxyrinchus",         "wikipedia_title": "Shortfin mako shark"},
    {"species_key": "carcharhinus_leucas",       "scientific_name": "Carcharhinus leucas",       "wikipedia_title": "Bull shark"},
    {"species_key": "carcharhinus_longimanus",   "scientific_name": "Carcharhinus longimanus",   "wikipedia_title": "Oceanic whitetip shark"},
    {"species_key": "triaenodon_obesus",         "scientific_name": "Triaenodon obesus",         "wikipedia_title": "Whitetip reef shark"},
    {"species_key": "carcharhinus_melanopterus", "scientific_name": "Carcharhinus melanopterus", "wikipedia_title": "Blacktip reef shark"},
    {"species_key": "somniosus_microcephalus",   "scientific_name": "Somniosus microcephalus",   "wikipedia_title": "Greenland shark"},
    {"species_key": "squalus_acanthias",         "scientific_name": "Squalus acanthias",         "wikipedia_title": "Spiny dogfish"},
    {"species_key": "heterodontus_francisci",    "scientific_name": "Heterodontus francisci",    "wikipedia_title": "Horn shark"},
    {"species_key": "carcharhinus_falciformis",  "scientific_name": "Carcharhinus falciformis",  "wikipedia_title": "Silky shark"},
    {"species_key": "alopias_vulpinus",          "scientific_name": "Alopias vulpinus",          "wikipedia_title": "Common thresher shark"},
    {"species_key": "ginglymostoma_cirratum",    "scientific_name": "Ginglymostoma cirratum",    "wikipedia_title": "Nurse shark"},
]

SEED_SCIENTIFIC_NAMES = [s["scientific_name"] for s in SEED_SPECIES]

# Unity Catalog organization (Databricks-centric).
CATALOG = "shark_knowledge"
SCHEMA_BRONZE = "bronze"
SCHEMA_SILVER = "silver"
SCHEMA_GOLD = "gold"

BRONZE_WIKIPEDIA = f"{CATALOG}.{SCHEMA_BRONZE}.wikipedia_raw"
BRONZE_GBIF_TAXONOMY = f"{CATALOG}.{SCHEMA_BRONZE}.gbif_taxonomy_raw"
BRONZE_GBIF_OCCURRENCE = f"{CATALOG}.{SCHEMA_BRONZE}.gbif_occurrence_raw"

SILVER_WIKIPEDIA = f"{CATALOG}.{SCHEMA_SILVER}.wikipedia_pages"
SILVER_GBIF_TAXONOMY = f"{CATALOG}.{SCHEMA_SILVER}.gbif_taxonomy"
SILVER_GBIF_OCCURRENCES = f"{CATALOG}.{SCHEMA_SILVER}.gbif_occurrences"
SILVER_REJECTED = f"{CATALOG}.{SCHEMA_SILVER}.rejected_records"

GOLD_SPECIES = f"{CATALOG}.{SCHEMA_GOLD}.species"
GOLD_SPECIES_CHUNKS = f"{CATALOG}.{SCHEMA_GOLD}.species_chunks"
