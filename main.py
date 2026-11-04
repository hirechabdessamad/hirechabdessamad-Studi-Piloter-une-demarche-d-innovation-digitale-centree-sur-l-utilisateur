#!/usr/bin/env python3
"""
GML Connect - preuve de concept locale
Modules : détection ZFE (Bounding Box + Ray Casting) et détection de freinage violent.
Dépendances : bibliothèque standard Python uniquement.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
LOGGER = logging.getLogger("gml_connect")


def load_json(path: Path) -> Any:
    """Charge un JSON et remonte une erreur explicite en cas de fichier invalide."""
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Fichier introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path} : {exc}") from exc


def validate_polygon(points: list[dict]) -> list[tuple[float, float]]:
    """Retourne les sommets sous forme (longitude, latitude)."""
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("Le polygone doit contenir au moins trois sommets.")
    vertices = []
    for index, point in enumerate(points):
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Sommet {index} invalide : lat/lon manquants ou non numériques.") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError(f"Coordonnées hors limites au sommet {index}.")
        vertices.append((lon, lat))
    if vertices[0] != vertices[-1]:
        vertices.append(vertices[0])
    return vertices


def point_on_segment(px: float, py: float, ax: float, ay: float,
                     bx: float, by: float, eps: float = 1e-10) -> bool:
    """Traite explicitement le cas d'un point situé sur le bord du polygone."""
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return (min(ax, bx) - eps <= px <= max(ax, bx) + eps and
            min(ay, by) - eps <= py <= max(ay, by) + eps)


def point_in_polygon(lon: float, lat: float,
                     vertices: list[tuple[float, float]]) -> bool:
    """
    Test Point-in-Polygon par Ray Casting.
    Convention : un point sur la frontière est considéré dans la zone (sécurité).
    """
    min_lon = min(p[0] for p in vertices)
    max_lon = max(p[0] for p in vertices)
    min_lat = min(p[1] for p in vertices)
    max_lat = max(p[1] for p in vertices)

    # Optimisation Bounding Box : rejet rapide si le point est hors du rectangle englobant.
    if lon < min_lon or lon > max_lon or lat < min_lat or lat > max_lat:
        return False

    inside = False
    for i in range(len(vertices) - 1):
        ax, ay = vertices[i]
        bx, by = vertices[i + 1]

        if point_on_segment(lon, lat, ax, ay, bx, by):
            return True

        # Le rayon horizontal part vers la droite. On inverse l'état à chaque croisement.
        intersects = ((ay > lat) != (by > lat))
        if intersects:
            crossing_lon = ax + (lat - ay) * (bx - ax) / (by - ay)
            if lon < crossing_lon:
                inside = not inside
    return inside


def run_geo(polygon_path: Path, gps_path: Path) -> list[dict]:
    vertices = validate_polygon(load_json(polygon_path))
    gps_points = load_json(gps_path)
    if not isinstance(gps_points, list):
        raise ValueError("Le fichier GPS doit contenir une liste de positions.")

    events = []
    previous_inside = False
    for point in gps_points:
        try:
            point_id = point.get("id")
            timestamp = str(point["timestamp"])
            lat, lon = float(point["lat"]), float(point["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("coordonnées GPS hors limites")
        except (KeyError, TypeError, ValueError) as exc:
            LOGGER.warning("Position GPS ignorée (%s) : %s", point.get("id", "?"), exc)
            continue

        inside = point_in_polygon(lon, lat, vertices)
        LOGGER.info("GPS #%s %s : %s", point_id, timestamp, "IN ZFE" if inside else "OUT ZFE")

        # L'alerte est émise à l'entrée, pas à chaque point restant dans la zone.
        if inside and not previous_inside:
            event = {
                "event": "ALERT ZFE",
                "point_id": point_id,
                "timestamp": timestamp,
                "latitude": lat,
                "longitude": lon,
                "message": "Entrée détectée dans le périmètre ZFE."
            }
            events.append(event)
            LOGGER.warning("[ALERT ZFE] Entrée détectée au point GPS #%s (%s).", point_id, timestamp)
        previous_inside = inside

    return events


def run_safety(csv_path: Path, output_path: Path, threshold: float = -2.5) -> dict:
    """
    Détecte un freinage si acc_y < seuil.
    Le sujet fournit un événement bref (une seule mesure à -3.45 m/s²) :
    un lissage temporel agressif risquerait de le supprimer. Le POC conserve
    donc la mesure longitudinale et applique le seuil physique explicite.
    """
    events = []
    samples = 0
    try:
        with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            required = {"timestamp", "acc_x", "acc_y", "acc_z"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("Le CSV doit contenir timestamp, acc_x, acc_y et acc_z.")

            for line_number, row in enumerate(reader, start=2):
                try:
                    timestamp = int(float(row["timestamp"]))
                    acc_x = float(row["acc_x"])
                    acc_y = float(row["acc_y"])
                    acc_z = float(row["acc_z"])
                    if not all(math.isfinite(v) for v in (acc_x, acc_y, acc_z)):
                        raise ValueError("mesure non finie")
                except (TypeError, ValueError, KeyError) as exc:
                    LOGGER.warning("Ligne CSV %s ignorée : %s", line_number, exc)
                    continue

                samples += 1
                # Axe Y = axe longitudinal ; une valeur négative forte indique un freinage.
                if acc_y < threshold:
                    event = {
                        "type": "HARSH_BRAKING",
                        "label": "Freinage violent",
                        "timestamp": timestamp,
                        "acc_y_m_s2": round(acc_y, 3),
                        "threshold_m_s2": threshold,
                        "severity": "high"
                    }
                    events.append(event)
                    LOGGER.warning("[SAFETY] Freinage violent détecté à %s : acc_y=%.2f m/s²",
                                   timestamp, acc_y)

    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Fichier introuvable : {csv_path}") from exc

    result = {
        "device": "GML-Connect-POC",
        "module": "Safety / Physics",
        "unit": "m/s²",
        "threshold": {"axis": "Y", "condition": "acc_y < threshold", "value": threshold},
        "samples_processed": samples,
        "harsh_braking_count": len(events),
        "events": events
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)
    LOGGER.info("Résultat Safety enregistré dans : %s", output_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="POC GML Connect : ZFE + Safety")
    parser.add_argument("--data-dir", type=Path, default=Path("data"),
                        help="Dossier contenant les trois fichiers d'entrée.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"),
                        help="Dossier de génération des résultats.")
    args = parser.parse_args()

    try:
        geo_events = run_geo(args.data_dir / "lyon_polygon.json",
                             args.data_dir / "truck_gps.json")
        safety_result = run_safety(args.data_dir / "accelerometer_data.csv",
                                   args.output_dir / "daily_score.json")
        geo_output = args.output_dir / "geo_events.json"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        geo_output.write_text(json.dumps(geo_events, indent=2, ensure_ascii=False), encoding="utf-8")

        print("\n=== BILAN DU POC GML CONNECT ===")
        print(f"Alertes ZFE générées : {len(geo_events)}")
        print(f"Freinages violents détectés : {safety_result['harsh_braking_count']}")
        print(f"Résultats : {args.output_dir.resolve()}")
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        LOGGER.error("Arrêt contrôlé du POC : %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
