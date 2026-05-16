#!/usr/bin/env python3
"""
Scrape Missing Categories — One-shot ingestion
═══════════════════════════════════════════════
Ejecuta catalog_scraper para las 4 categorías de Automotriz
que faltan en THULE_CATEGORIES (IDs 5xxx de OpenCart).

Uso:
  python3 scrape_missing_categories.py              # full scrape
  python3 scrape_missing_categories.py --dry-run     # solo descubrir, no escribir DB
  python3 scrape_missing_categories.py --max-products 10  # limitar para test
"""
import sys
from pathlib import Path

# Asegurar que el directorio scripts/ esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from catalog_scraper import main

MISSING_CATEGORIES = [
    "3_5139",   # Alfombras (WeatherTech FloorLiners, Cargo Liners)
    "3_5176",   # Limpieza y Mantenimiento (WeatherTech cleaning products)
    "3_5180",   # Deflectores (WeatherTech Side Window Deflectors)
    "3_5181",   # Sistemas de Remolque (CURT towing systems)
]

if __name__ == "__main__":
    # Pasar las categorías faltantes + cualquier arg extra del CLI
    extra_args = sys.argv[1:]
    args = ["--categories"] + MISSING_CATEGORIES + extra_args
    sys.exit(main(args))
