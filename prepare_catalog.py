"""
Chunk 1 - Catalog Prep
Loads raw catalog JSON, adds test_type and search_text, saves catalog_prepared.json
"""

import json
import os

from config import settings

# KEY_MAP is centralised in config.py (settings.key_map)
KEY_MAP = settings.key_map


def derive_test_type(keys):
    """
    Converts a list of category names to a comma-separated code string.
    Example: ["Personality & Behavior", "Competencies"] -> "P,C"
    """
    codes = []

    for key in keys:
        code = KEY_MAP.get(key)

        if code is None:
            continue  # skip unknown keys

        if code not in codes:
            codes.append(code)  # no duplicates

    if len(codes) == 0:
        return settings.default_test_type_code  # fallback

    return ",".join(codes)


def build_search_text(item):
    """
    Builds the string that will be turned into an embedding vector.
    We combine name + categories + job levels + description
    so queries like "senior Java developer" can match the right items.
    """
    name        = item.get("name", "")
    keys_str    = ", ".join(item.get("keys", []))
    levels_str  = ", ".join(item.get("job_levels", []))
    description = item.get("description", "")

    # Join all parts with a period separator
    parts = [name, keys_str, levels_str, description]

    # Remove any empty strings before joining
    parts = [p for p in parts if p.strip()]

    search_text = ". ".join(parts)
    return search_text


def prepare_catalog(input_path, output_path):
    # Load the raw JSON file
    print(f"Loading: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        raw_catalog = json.load(f)
    print(f"Loaded {len(raw_catalog)} items")

    prepared = []

    for item in raw_catalog:
        # Skip any item missing the two fields we absolutely need
        if not item.get("name"):
            continue
        if not item.get("link"):
            continue

        # Add test_type field
        item["test_type"] = derive_test_type(item.get("keys", []))

        # Add search_text field
        item["search_text"] = build_search_text(item)

        prepared.append(item)

    print(f"Prepared {len(prepared)} items")

    # Save to output file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prepared, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {output_path}")


# Entry point
INPUT_PATH  = settings.resolve_path(settings.raw_catalog_path)
OUTPUT_PATH = settings.resolve_path(settings.prepared_catalog_path)

prepare_catalog(INPUT_PATH, OUTPUT_PATH)

# I have not added a fall back for empty description as 
# provided data had no empty description or any fields as such.
