# GML Connect – Preuve de concept (POC)

## 1. Objectif

Ce prototype Python démontre deux fonctions essentielles de la tablette télématique GML Connect :

- **Module Geo / ZFE** : déterminer si une position GPS se trouve dans le polygone ZFE de Lyon, y compris sans appel à un service cartographique en ligne.
- **Module Safety / Physics** : lire les mesures d'accéléromètre et détecter un freinage violent à partir de l'axe longitudinal Y.

Le projet utilise uniquement la bibliothèque standard de Python : aucune dépendance externe n'est nécessaire.

## 2. Arborescence

```text
GML_Connect_POC/
├── main.py
├── README.md
├── data/
│   ├── lyon_polygon.json
│   ├── truck_gps.json
│   └── accelerometer_data.csv
└── output/                  # créé automatiquement à l'exécution
    ├── geo_events.json
    └── daily_score.json
```

## 3. Prérequis

- Python 3.9 ou supérieur recommandé.
- Aucun `pip install` nécessaire.

Vérifier la version :

```bash
python --version
```

## 4. Exécution

Depuis le dossier `GML_Connect_POC` :

```bash
python main.py
```

Si la commande `python` n'est pas reconnue sous macOS/Linux :

```bash
python3 main.py
```

Pour choisir d'autres dossiers :

```bash
python main.py --data-dir data --output-dir output
```

## 5. Fonctionnement des algorithmes

### Module 1 – Géolocalisation ZFE

1. Le programme charge `lyon_polygon.json`, qui contient les sommets du périmètre.
2. Il calcule la **Bounding Box** : latitude et longitude minimales et maximales.
3. Chaque position du camion est d'abord comparée à ce rectangle englobant. Si elle est à l'extérieur, le point est immédiatement rejeté.
4. Si elle est à l'intérieur de la Bounding Box, le programme applique le **Ray Casting** : un rayon horizontal part du point et le nombre de croisements avec les côtés du polygone détermine si le point est dedans ou dehors.
5. Une alerte `[ALERT ZFE]` est produite lors du passage de l'état extérieur à l'état intérieur. Les points suivants dans la même zone ne génèrent pas une nouvelle alerte.

Un point situé exactement sur le bord est considéré comme étant dans la zone, par choix prudent pour la sécurité réglementaire.

### Module 2 – Analyse Safety

1. Le programme lit le CSV et vérifie la présence des colonnes `timestamp`, `acc_x`, `acc_y` et `acc_z`.
2. Il utilise l'axe Y, défini dans l'énoncé comme l'axe longitudinal du véhicule.
3. Une valeur `acc_y < -2.5 m/s²` déclenche un événement « Freinage violent ».
4. Les événements sont enregistrés dans `output/daily_score.json`.

**Précision sur le filtrage :** l'annexe fournit un événement bref, sur une seule mesure (`-3.45 m/s²`). Un lissage par moyenne ou médiane pourrait effacer ce pic réel. Pour ne pas masquer l'événement explicitement attendu, ce POC applique donc le seuil directement à la mesure longitudinale, écarte les lignes mal formées et les valeurs non numériques/non finies. En production, le filtrage devra être calibré sur des données réelles, à fréquence connue, et validé pour distinguer les chocs/vibrations des freinages.

## 6. Résultats attendus avec les données fournies

- Les deux premières positions GPS sont à l'extérieur du polygone.
- Le calcul géométrique place les points GPS n°1, n°2 et n°3 à l'extérieur ; le point n°4 est le premier point à l'intérieur et déclenche `[ALERT ZFE]`.
- Le point n°5 reste dans la zone sans répéter l'alerte d'entrée.

**Écart relevé dans l'annexe :** le champ `expected` du jeu de test indique `IN (Bordure)` pour le point n°3. Or, avec les coordonnées exactes du polygone fournies dans la même annexe, ce point est géométriquement à l'extérieur. Le POC applique le calcul au polygone plutôt que de forcer le résultat attendu. Cet écart doit être signalé et arbitré avant validation métier.
- Le CSV contient un freinage violent à `1678880005`, avec `acc_y = -3.45 m/s²`.
- `daily_score.json` contient un événement `HARSH_BRAKING`.

Les fichiers de sortie sont générés automatiquement dans `output/`.

## 7. Gestion des erreurs

Le programme gère notamment :
- fichier d'entrée absent ;
- JSON mal formé ;
- polygone ou coordonnées invalides ;
- colonnes CSV manquantes ;
- lignes CSV non numériques ou non exploitables.

Les lignes invalides sont ignorées avec un avertissement lorsque cela est possible. Une erreur bloquante provoque un arrêt contrôlé avec un message explicite, plutôt qu'une trace d'erreur incompréhensible.

## 8. Limites du POC

Ce prototype valide la logique sur le jeu de données fourni. Il ne constitue pas encore une version industrielle :
- les coordonnées ZFE sont un polygone simplifié de Lyon, pas une cartographie européenne complète ;
- les positions GPS et mesures capteurs sont des données de test ;
- le POC ne pilote pas encore les capteurs physiques Android ;
- la synchronisation réseau, le chiffrement, la gestion des comptes et l'interface conducteur ne sont pas inclus.

Le prototype démontre la faisabilité algorithmique locale des deux traitements principaux. Des essais sur tablette Zebra ET40 et des données terrain seront nécessaires avant le déploiement.
