#!/usr/bin/env python3
"""
FamilyMeal → Google Sheets writer
────────────────────────────────────────────────────────────────
Lit  : familymeal_data.json  (généré par le scheduled task Claude)
Écrit: Google Sheets FamilyPlan-DATABASE (4 onglets)
Mode : HISTORIQUE — chaque run ajoute une nouvelle semaine.
       Les données des semaines précédentes sont conservées.

Onglets cibles :
  Menus       → Semaine, Jour, Titre recette, URL, Site source,
                Protéine, Temps (min), Portions, Statut
  Circulaires → Semaine, Épicerie, Produit, Catégorie,
                Prix promo, Prix régulier, Économie %
  Épicerie    → Semaine, Produit, Quantité, Unité, Prix, Catégorie,
                Épicerie recommandée, Imbattable Maxi
  Statut      → Valeur (A2) = "READY - AAAA-MM-JJ | N semaine(s) archivée(s)"
────────────────────────────────────────────────────────────────
"""

import subprocess, sys, json, os
from datetime import datetime

# ── Auto-install des dépendances si absentes ───────────────────
def install(pkg):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", pkg,
         "--break-system-packages", "-q"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    print("   Installation de gspread...")
    install("gspread")
    install("google-auth")
    import gspread
    from google.oauth2.service_account import Credentials

# ── Configuration ──────────────────────────────────────────────
SHEET_ID   = "1HOpW3Fj0MzQ4yNF5OohFHxJjjFVOrnwsJnSn7fTt-38"
SCOPES     = ["https://www.googleapis.com/auth/spreadsheets"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
DATA_FILE  = os.path.join(SCRIPT_DIR, "familymeal_data.json")


# ── Connexion ──────────────────────────────────────────────────
def get_client():
    if not os.path.exists(CREDS_FILE):
        raise FileNotFoundError(
            f"credentials.json introuvable dans : {SCRIPT_DIR}\n"
            "Télécharge-le depuis Google Cloud Console et place-le ici."
        )
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


# ── Upsert générique (mode historique) ────────────────────────
def upsert_tab(ws, headers, new_rows, semaine):
    """
    Mise à jour incrémentale :
    1. Lit toutes les lignes existantes
    2. Supprime celles de la semaine actuelle (re-run propre)
    3. Ajoute les nouvelles lignes en tête (semaine la plus récente en haut)
    4. Réécrit tout
    Retourne le nombre de semaines distinctes archivées.
    """
    existing = ws.get_all_values()
    kept_rows = [row for row in existing[1:] if row and row[0] != semaine]
    all_rows = new_rows + kept_rows
    ws.clear()
    ws.update("A1", [headers] + all_rows)
    semaines = set(row[0] for row in all_rows if row and row[0])
    return len(semaines)


# ── Onglet Menus ───────────────────────────────────────────────
def write_menus(sheet, menus, semaine):
    ws = sheet.worksheet("Menus")
    headers = ["Semaine", "Jour", "Titre", "URL", "Site",
               "Protéine", "Temps (min)", "Portions", "Statut"]
    new_rows = []
    for m in menus:
        new_rows.append([
            semaine,
            m.get("jour", ""),
            m.get("titre", ""),
            m.get("url", ""),
            m.get("site", ""),
            m.get("proteine", ""),
            m.get("temps", ""),
            m.get("portions", ""),
            m.get("statut", "Suggéré"),
        ])
    n = upsert_tab(ws, headers, new_rows, semaine)
    print(f"   ✓ Menus : {len(new_rows)} recettes | {n} semaine(s) archivée(s)")
    return n


# ── Onglet Circulaires ─────────────────────────────────────────
def write_circulaires(sheet, circulaires, semaine):
    ws = sheet.worksheet("Circulaires")
    headers = ["Semaine", "Épicerie", "Produit", "Catégorie",
               "Prix promo", "Prix régulier", "Économie %"]
    new_rows = []
    for c in circulaires:
        new_rows.append([
            semaine,
            c.get("epicerie", ""),
            c.get("produit", ""),
            c.get("categorie", ""),
            c.get("prix_promo", ""),
            c.get("prix_regulier", ""),
            c.get("economie_pct", ""),
        ])
    n = upsert_tab(ws, headers, new_rows, semaine)
    print(f"   ✓ Circulaires : {len(new_rows)} items | {n} semaine(s) archivée(s)")


# ── Onglet Épicerie ────────────────────────────────────────────
def write_epicerie(sheet, epicerie, semaine):
    ws = sheet.worksheet("Épicerie")
    headers = ["Semaine", "Produit", "Quantité", "Unité", "Prix",
               "Catégorie", "Épicerie recommandée", "Imbattable Maxi"]
    new_rows = []
    for item in epicerie:
        imbattable = item.get("imbattable_maxi", "")
        if isinstance(imbattable, bool):
            imbattable = "OUI" if imbattable else ""
        new_rows.append([
            semaine,
            item.get("produit", ""),
            item.get("quantite", ""),
            item.get("unite", ""),
            item.get("prix", ""),
            item.get("categorie", ""),
            item.get("epicerie", ""),
            imbattable,
        ])
    n = upsert_tab(ws, headers, new_rows, semaine)
    print(f"   ✓ Épicerie : {len(new_rows)} items | {n} semaine(s) archivée(s)")


# ── Onglet Statut ──────────────────────────────────────────────
def write_statut(sheet, semaine, n_semaines):
    ws = sheet.worksheet("Statut")
    ws.update("A2", [[f"READY - {semaine} | {n_semaines} semaine(s) archivée(s)"]])
    print(f"   ✓ Statut : READY - {semaine} | {n_semaines} semaine(s) archivée(s)")


# ── Main ───────────────────────────────────────────────────────
def main():
    print("\n📊 FamilyMeal → Google Sheets (mode historique)")
    print("─" * 50)

    if not os.path.exists(DATA_FILE):
        print(f"❌ Fichier introuvable : {DATA_FILE}")
        print("   Assure-toi que le scheduled task a bien généré familymeal_data.json")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    semaine = data.get("semaine", datetime.today().strftime("%Y-%m-%d"))
    print(f"   Semaine    : {semaine}")
    print(f"   Menus      : {len(data.get('menus', []))}")
    print(f"   Circulaires: {len(data.get('circulaires', []))}")
    print(f"   Épicerie   : {len(data.get('epicerie', []))}")
    print()

    print("   Connexion à Google Sheets...")
    try:
        client = get_client()
        sheet  = client.open_by_key(SHEET_ID)
    except Exception as e:
        print(f"❌ Connexion échouée : {e}")
        sys.exit(1)

    n_semaines = write_menus(sheet, data.get("menus", []), semaine)
    write_circulaires(sheet, data.get("circulaires", []), semaine)
    write_epicerie(sheet, data.get("epicerie", []), semaine)
    write_statut(sheet, semaine, n_semaines)

    print()
    print(f"✅ Google Sheets mis à jour avec succès !")
    print(f"   https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    main()
