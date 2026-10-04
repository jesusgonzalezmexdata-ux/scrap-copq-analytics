"""Catálogo y supuestos de la planta ficticia (datos sintéticos)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"

SEED = 42
YEAR = 2025
SHIFTS = ["Matutino", "Vespertino", "Nocturno"]
SHIFT_HOURS = 7.5

# Días de descanso obligatorio (LFT art. 74) que caen en día laborable en 2025.
HOLIDAYS = ["2025-01-01", "2025-02-03", "2025-03-17", "2025-05-01",
            "2025-09-16", "2025-11-17", "2025-12-25"]

LINES = {
    "L1": {"proceso": "Estampado", "productos": ["REF-420", "MNS-530"],
           "piezas_turno": (2400, 3000), "scrap_base": 0.016, "retrabajo_base": 0.020,
           "intervalo_pm_h": 320, "proveedores": {"A": 0.55, "B": 0.33, "C": 0.12}},
    "L2": {"proceso": "Soldadura robotizada", "productos": ["SOP-101", "TRV-310"],
           "piezas_turno": (700, 900), "scrap_base": 0.014, "retrabajo_base": 0.018,
           "intervalo_pm_h": 320, "proveedores": {"A": 0.70, "B": 0.30}},
    "L3": {"proceso": "Soldadura manual", "productos": ["BRK-205", "BAS-615"],
           "piezas_turno": (340, 440), "scrap_base": 0.020, "retrabajo_base": 0.025,
           "intervalo_pm_h": 320, "proveedores": {"A": 0.70, "B": 0.30}},
}

# producto: (descripción, material, conversión, retrabajo, precio) en MXN por pieza
PRODUCTS = {
    "REF-420": ("Refuerzo de puerta", 38, 14, 9, 92),
    "MNS-530": ("Ménsula de escape", 26, 11, 7, 64),
    "SOP-101": ("Soporte de motor", 95, 42, 22, 238),
    "TRV-310": ("Travesaño", 140, 55, 28, 330),
    "BRK-205": ("Brazo de suspensión", 120, 61, 30, 298),
    "BAS-615": ("Base de batería", 72, 35, 18, 176),
}

# Mezcla base de defectos por proceso (participación en el scrap).
DEFECTS = {
    "Estampado": {"Rebaba": 0.35, "Dimensional": 0.30, "Grieta": 0.15, "Daño superficial": 0.20},
    "Soldadura robotizada": {"Porosidad": 0.35, "Falta de fusión": 0.15, "Dimensional": 0.30,
                             "Perforación": 0.20},
    "Soldadura manual": {"Porosidad": 0.30, "Falta de fusión": 0.25, "Dimensional": 0.25,
                         "Socavado": 0.20},
}

# Humedad relativa media mensual (%), clima típico del altiplano poblano.
HUMIDITY_BY_MONTH = {1: 50, 2: 45, 3: 42, 4: 45, 5: 52, 6: 68,
                     7: 72, 8: 74, 9: 76, 10: 66, 11: 58, 12: 54}

# Supuestos de costo para el simulador de ahorro (MXN).
PM_COST_MXN = 4_500            # cambio de consumibles y calibración de antorcha en L2
TRAINING_COST_MXN = 15_000     # inducción por competencias por operador nuevo
SUPPLIER_C_DISCOUNT = 0.02     # el proveedor C es 2 % más barato en material
NEW_OPERATOR_MONTHS = 6        # antigüedad que define "operador nuevo"
