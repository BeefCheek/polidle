#!/usr/bin/env python3
"""
Polidle Data Scraper
====================
Downloads French politician data and official photos.

Data sources:
    - Deputies:  data.assemblee-nationale.fr open data (17th legislature)
    - Senators:  senat.fr list page + data.senat.fr API

Usage:
    pip install -r requirements.txt
    python scripts/scrape.py
"""

import io
import json
import re
import sys
import time
import unicodedata
import zipfile
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = BASE_DIR / "photos"

# AN open data – current legislature deputies + organes
AN_OPENDATA_ZIP = (
    "https://data.assemblee-nationale.fr/static/openData/repository/17/"
    "amo/deputes_actifs_mandats_actifs_organes/"
    "AMO10_deputes_actifs_mandats_actifs_organes.json.zip"
)

# AN official photos – best available (240×240 square)
AN_PHOTO_URL = "https://www.assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/{pa_id}.jpg"

# Sénat
SENAT_LIST_URL = "https://www.senat.fr/senateurs/senatl.html"
SENAT_DATA_URL = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Polidle/1.0 (Educational game about French politics)",
})

# Sénat group name → sigle mapping
SENAT_GROUP_SIGLE = {
    "Les Républicains": "LR",
    "Les Indépendants": "INDEP",
    "Les Indépendants - République et Territoires": "INDEP",
    "Non inscrit": "NI",
    "Non inscrits": "NI",
}

# Sénat group sigle → full name
SENAT_GROUP_NAME = {
    "LR": "Les Républicains",
    "SER": "Socialiste, Écologiste et Républicain",
    "UC": "Union Centriste",
    "INDEP": "Les Indépendants – République et Territoires",
    "RDPI": "Rassemblement des démocrates, progressistes et indépendants",
    "CRCE-K": "Communiste Républicain Citoyen Écologiste – Kanaky",
    "RDSE": "Rassemblement Démocratique et Social Européen",
    "GEST": "Écologiste – Solidarité et Territoires",
    "NI": "Non-inscrits",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_directories():
    for d in [DATA_DIR, PHOTOS_DIR / "deputes", PHOTOS_DIR / "senateurs"]:
        d.mkdir(parents=True, exist_ok=True)


def slugify(text):
    """Convert a name to a URL-friendly slug."""
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def fetch_json(url, label="data"):
    print(f"  → Fetching {label}… {url}")
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"    ✗ Error: {exc}")
        return None


def fetch_html(url, label="page"):
    print(f"  → Fetching {label}… {url}")
    try:
        resp = SESSION.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"    ✗ Error: {exc}")
        return None


def fetch_zip(url, label="archive"):
    """Download a zip file and return a ZipFile object, or None on error."""
    print(f"  → Downloading {label}… {url}")
    try:
        resp = SESSION.get(url, timeout=60)
        resp.raise_for_status()
        return zipfile.ZipFile(io.BytesIO(resp.content))
    except (requests.RequestException, zipfile.BadZipFile) as exc:
        print(f"    ✗ Error: {exc}")
        return None


# ---------------------------------------------------------------------------
# Deputies (data.assemblee-nationale.fr open data)
# ---------------------------------------------------------------------------

def parse_deputes_opendata(zf):
    """Parse deputies from the AN open data zip file."""
    if zf is None:
        return []

    # 1. Build organe lookup: organe_uid -> {sigle, nom}
    organe_map = {}
    for name in zf.namelist():
        if name.startswith("json/organe/") and name.endswith(".json"):
            data = json.loads(zf.read(name))
            org = data.get("organe", data)
            if org.get("codeType") == "GP":
                uid = org.get("uid", "")
                organe_map[uid] = {
                    "sigle": org.get("libelleAbrege", ""),
                    "nom": org.get("libelle", ""),
                }

    # 2. Parse each deputy
    result = []
    for name in zf.namelist():
        if not (name.startswith("json/acteur/") and name.endswith(".json")):
            continue

        data = json.loads(zf.read(name))
        act = data.get("acteur", data)

        # Get PA ID
        uid_info = act.get("uid", {})
        pa_id = uid_info.get("#text", "") if isinstance(uid_info, dict) else str(uid_info)
        if not pa_id:
            continue

        # Identity
        ident = act.get("etatCivil", {}).get("ident", {})
        nom = ident.get("nom", "")
        prenom = ident.get("prenom", "")
        nom_complet = f"{prenom} {nom}".strip()

        # Find active 17th legislature group
        mandats = act.get("mandats", {}).get("mandat", [])
        if not isinstance(mandats, list):
            mandats = [mandats]

        groupe_sigle = "NI"
        groupe_nom = "Non inscrit"
        for m in mandats:
            if not isinstance(m, dict):
                continue
            if (m.get("typeOrgane") == "GP"
                    and m.get("legislature") == "17"
                    and m.get("dateFin") is None):
                organe_ref = m.get("organes", {}).get("organeRef", "")
                if organe_ref in organe_map:
                    groupe_sigle = organe_map[organe_ref]["sigle"]
                    groupe_nom = organe_map[organe_ref]["nom"]
                break

        # Build slug for filename
        slug = slugify(nom_complet)

        # Photo URL (numeric part of PA ID)
        pa_num = pa_id.replace("PA", "")

        result.append({
            "id": slug,
            "nom": nom,
            "prenom": prenom,
            "nom_complet": nom_complet,
            "groupe_sigle": groupe_sigle,
            "groupe_nom": groupe_nom,
            "photo_url": AN_PHOTO_URL.format(pa_id=pa_num),
            "type": "depute",
            "photo": "",
        })

    return result


# ---------------------------------------------------------------------------
# Senators (senat.fr + data.senat.fr)
# ---------------------------------------------------------------------------

def _extract_matricule(slug):
    """Extract the matricule (e.g. '21071f') from a senator slug."""
    m = re.search(r'(\d+[a-z])$', slug)
    return m.group(1) if m else ""


def parse_senateurs(html_list, json_data):
    """
    Combine data from:
      - The senat.fr senator list page (slugs + display names)
      - data.senat.fr JSON (political group, etc.)
    """
    if not html_list:
        return []

    # --- Build group lookup from data.senat.fr (keyed by matricule upper) ---
    group_by_matricule = {}
    if json_data:
        for rec in json_data.get("results", []):
            if rec.get("Etat") != "ACTIF":
                continue
            mat = rec.get("Matricule", "").upper()
            raw_group = rec.get("Groupe_politique", "NI") or "NI"
            sigle = SENAT_GROUP_SIGLE.get(raw_group, raw_group)
            nom = SENAT_GROUP_NAME.get(sigle, raw_group)
            group_by_matricule[mat] = (sigle, nom)

    # --- Parse senator links from list page ---
    pattern = re.compile(
        r'href="/senateur/([^"]+?)\.html"[^>]*>([^<]+)</[Aa]>',
        re.IGNORECASE,
    )

    result = []
    for match in pattern.finditer(html_list):
        slug = match.group(1).strip()
        raw_name = match.group(2).strip().replace("\xa0", " ").replace("&nbsp;", " ")

        matricule = _extract_matricule(slug).upper()

        parts = raw_name.split(None, 1)
        if len(parts) == 2:
            nom_display, prenom = parts
        else:
            nom_display = parts[0] if parts else slug
            prenom = ""

        nom = nom_display.title()
        nom_complet = f"{prenom} {nom}".strip()

        groupe_sigle, groupe_nom = group_by_matricule.get(matricule, ("NI", "Non-inscrits"))

        result.append({
            "id": slug,
            "nom": nom,
            "prenom": prenom,
            "nom_complet": nom_complet,
            "groupe_sigle": groupe_sigle,
            "groupe_nom": groupe_nom,
            "photo_url": f"https://www.senat.fr/senimg/{slug}_carre.jpg",
            "type": "senateur",
            "photo": "",
        })

    return result


# ---------------------------------------------------------------------------
# Photo download
# ---------------------------------------------------------------------------

def download_photo(url, filepath, retries=2):
    if filepath.exists() and filepath.stat().st_size > 500:
        return True

    for attempt in range(retries + 1):
        try:
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 500:
                ct = resp.headers.get("content-type", "")
                if "image" in ct or "octet" in ct or resp.content[:3] in (b'\xff\xd8\xff', b'\x89PN'):
                    filepath.write_bytes(resp.content)
                    return True
        except requests.RequestException:
            pass
        if attempt < retries:
            time.sleep(0.5)

    return False


def download_photos(politicians, subdir):
    photo_dir = PHOTOS_DIR / subdir
    total = len(politicians)
    ok, fail = 0, 0

    print(f"\n📸 Downloading {subdir} photos ({total} total)…")

    for i, pol in enumerate(politicians):
        fp = photo_dir / f"{pol['id']}.jpg"

        urls = pol.get("photo_urls") or ([pol["photo_url"]] if pol.get("photo_url") else [])
        downloaded = False
        for url in urls:
            if download_photo(url, fp):
                downloaded = True
                break

        if downloaded:
            pol["photo"] = f"photos/{subdir}/{pol['id']}.jpg"
            ok += 1
        else:
            pol["photo"] = ""
            fail += 1

        if (i + 1) % 25 == 0 or i + 1 == total:
            pct = int((i + 1) / total * 100)
            print(f"  [{i+1:>4}/{total}] {pct:3d}%  ✓ {ok}  ✗ {fail}")

        if (i + 1) % 10 == 0:
            time.sleep(0.3)

    print(f"  Done: {ok} downloaded, {fail} failed")
    return [p for p in politicians if p["photo"]]


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_json(politicians, filename):
    fp = DATA_DIR / filename
    skip_keys = {"photo_url", "photo_urls"}
    clean = [{k: v for k, v in p.items() if k not in skip_keys} for p in politicians]
    fp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Saved {len(clean)} entries → {fp}")


def print_stats(politicians, label):
    groups = {}
    for p in politicians:
        g = p.get("groupe_sigle", "?")
        groups[g] = groups.get(g, 0) + 1

    print(f"\n📊 {label} groups:")
    for g, c in sorted(groups.items(), key=lambda x: -x[1]):
        print(f"  {g:14s} {c:>4}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 55)
    print("  POLIDLE — Data Scraper")
    print("=" * 55)

    setup_directories()

    # ── Deputies (AN open data) ───────────────────────────────
    print("\n🟦 ASSEMBLÉE NATIONALE (17e législature)")
    zf = fetch_zip(AN_OPENDATA_ZIP, "open data archive")
    deputes = parse_deputes_opendata(zf) if zf else []
    print(f"  Parsed {len(deputes)} deputies")

    # ── Senators ──────────────────────────────────────────────
    print("\n🟥 SÉNAT")
    sen_html = fetch_html(SENAT_LIST_URL, "senator list")
    sen_data = fetch_json(SENAT_DATA_URL, "senator groups (data.senat.fr)")
    senateurs = parse_senateurs(sen_html, sen_data)
    print(f"  Parsed {len(senateurs)} senators")

    if not deputes and not senateurs:
        print("\n❌ No data fetched. Check your internet connection.")
        sys.exit(1)

    # ── Download photos ───────────────────────────────────────
    if deputes:
        deputes = download_photos(deputes, "deputes")
    if senateurs:
        senateurs = download_photos(senateurs, "senateurs")

    # ── Save ──────────────────────────────────────────────────
    if deputes:
        save_json(deputes, "deputes.json")
        print_stats(deputes, "Deputies")
    if senateurs:
        save_json(senateurs, "senateurs.json")
        print_stats(senateurs, "Senators")

    # ── Summary ───────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"  ✅ Done!  {len(deputes)} deputies  •  {len(senateurs)} senators")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()
