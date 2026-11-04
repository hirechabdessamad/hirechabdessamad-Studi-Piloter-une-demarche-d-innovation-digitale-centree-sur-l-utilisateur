# Dossier 4 – Présentation et justification du POC

## Démarche de réalisation

Le POC a été développé en Python afin de valider rapidement les deux traitements critiques identifiés dans le Product Backlog. Le choix d'un prototype local, sans dépendance externe, facilite sa reproduction et sa démonstration.

### Choix du module Geo

Le périmètre ZFE est représenté par un polygone et non par un simple rectangle. Le test Point-in-Polygon est donc nécessaire. La Bounding Box constitue un filtre préalable peu coûteux : elle évite d'exécuter le Ray Casting pour les points manifestement éloignés de la zone. Le Ray Casting examine ensuite les intersections d'un rayon avec les arêtes du polygone.

Pour un polygone de M sommets, le test Ray Casting est en O(M) par position. Le calcul de la Bounding Box est réalisé une fois au chargement du polygone ; le test rectangulaire est en O(1). Cette organisation évite un traitement quadratique et reste adaptée à une tablette aux ressources limitées, sous réserve de mesurer les performances avec la cartographie réelle.

### Choix du module Safety

L'énoncé définit l'axe Y comme axe longitudinal et indique qu'une valeur négative forte correspond à un freinage. Le seuil demandé dans l'annexe est donc `acc_y < -2.5 m/s²`. Le POC détecte l'échantillon à -3.45 m/s² et l'inscrit dans un résultat JSON structuré.

L'extrait fourni contient un événement très court, sur un seul échantillon. Un filtre de moyenne glissante ou une médiane pourrait le supprimer. Le prototype évite donc un lissage arbitraire et applique le seuil à la mesure Y après validation des données. Ce choix est explicitement limité au jeu de test ; la version industrielle devra calibrer un filtrage sur des mesures terrain, la fréquence d'échantillonnage et les caractéristiques du montage de la tablette.

### Résultats de démonstration

Avec les fichiers de l'annexe :
- une alerte d'entrée ZFE est produite au point GPS n°4 ;
- le point n°3 est calculé à l'extérieur, malgré son champ `expected` indiquant `IN (Bordure)` dans l'annexe ;
- le point n°5 reste dans la zone sans répéter l'alerte d'entrée ;
- un freinage violent est détecté à l'horodatage `1678880005`, avec `acc_y = -3.45 m/s²` ;
- les résultats sont exportés dans `output/geo_events.json` et `output/daily_score.json`.

### Conclusion

Le POC démontre la faisabilité des deux traitements essentiels sur les données de test : géolocalisation dans un polygone et détection d'un freinage violent. Il met également en évidence une incohérence entre le résultat attendu fourni pour le point GPS n°3 et sa position réelle par rapport au polygone. Cette anomalie doit être clarifiée avec le jeu de données avant de considérer le test métier comme entièrement conforme. Il constitue une première validation technique, mais ne remplace pas les tests sur la tablette Zebra ET40, avec des capteurs réels, une cartographie complète et des conditions de conduite représentatives.
