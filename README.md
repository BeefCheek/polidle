# 🏛️ Polidle

Devine le groupe politique des parlementaires français à partir de leur photo officielle.

**[Jouer →](https://polidle.com)**

## Principe

Une photo d'un·e député·e ou sénateur·rice s'affiche. Tu cliques sur le bouton du bon groupe politique. C'est tout.

- 618 député·e·s (Assemblée Nationale)
- 348 sénateur·rice·s (Sénat)
- Score, série en cours & record
- Filtre par chambre (Tous / Assemblée / Sénat)
- Navigation clavier (1-9 pour choisir, Entrée/Espace pour suivant)

## Stack technique

- **Frontend :** HTML/CSS/JS statique — pas de framework, pas de build
- **Scraper :** Python (`requests` + `beautifulsoup4`)
- **Hébergement :** GitHub Pages (gratuit)
- **Analytics :** [GoatCounter](https://www.goatcounter.com) (respectueux de la vie privée, sans cookies)

## Sources des données

| Données | Source |
|---|---|
| Liste & groupes des députés | [nosdeputes.fr](https://www.nosdeputes.fr) |
| Photos des députés | [assemblee-nationale.fr](https://www.assemblee-nationale.fr) (portraits officiels) |
| Liste & groupes des sénateurs | [data.senat.fr](https://data.senat.fr) |
| Photos des sénateurs | [senat.fr](https://www.senat.fr) (portraits officiels) |

## Mettre à jour les données

```bash
pip install -r requirements.txt
python scripts/scrape.py
```

Retélécharge toutes les données et photos depuis les sources officielles.

## Lancer en local

```bash
python3 -m http.server 8080
# Ouvrir http://localhost:8080
```

## Licence

MIT
