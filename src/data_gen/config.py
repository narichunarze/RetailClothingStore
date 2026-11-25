"""Catálogo del negocio simulado: países, tiendas, categorías, tallas y colores."""

COUNTRIES = {
    # code: (moneda, hemisferio, ciudades [(ciudad, lat, lon)])
    "PE": ("PEN", "S", [("Lima", -12.05, -77.04), ("Arequipa", -16.41, -71.54)]),
    "CL": ("CLP", "S", [("Santiago", -33.45, -70.67), ("Concepcion", -36.83, -73.05)]),
    "CO": ("COP", "EQ", [("Bogota", 4.71, -74.07), ("Medellin", 6.24, -75.58)]),
    "MX": ("MXN", "N", [("CDMX", 19.43, -99.13), ("Monterrey", 25.69, -100.32)]),
}

# Precio base aproximado en USD; el generador lo convierte a moneda local.
FX_TO_LOCAL = {"PEN": 3.7, "CLP": 950.0, "COP": 4000.0, "MXN": 18.0}

# category: (season, rango precio USD, tallas, demanda base relativa)
#   season: "summer" | "winter" | "all"
APPAREL_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
SHOE_SIZES = ["36", "37", "38", "39", "40", "41", "42", "43"]

CATEGORIES = {
    "polos": ("summer", (12, 25), APPAREL_SIZES, 1.4),
    "shorts": ("summer", (15, 30), APPAREL_SIZES, 0.9),
    "vestidos": ("summer", (25, 60), APPAREL_SIZES, 0.7),
    "casacas": ("winter", (45, 120), APPAREL_SIZES, 0.6),
    "chompas": ("winter", (25, 55), APPAREL_SIZES, 0.8),
    "jeans": ("all", (30, 70), APPAREL_SIZES, 1.2),
    "camisas": ("all", (20, 45), APPAREL_SIZES, 0.9),
    "calzado": ("all", (40, 110), SHOE_SIZES, 0.6),
}

# Curva de tallas: participación de cada talla en la demanda del modelo.
SIZE_CURVE = {
    "XS": 0.06, "S": 0.18, "M": 0.30, "L": 0.26, "XL": 0.14, "XXL": 0.06,
    "36": 0.08, "37": 0.12, "38": 0.16, "39": 0.17, "40": 0.17, "41": 0.14, "42": 0.10, "43": 0.06,
}

COLORS = ["negro", "blanco", "azul", "gris", "beige", "rojo", "verde"]
COLOR_WEIGHT = {"negro": 1.4, "blanco": 1.2, "azul": 1.2, "gris": 1.0,
                "beige": 0.8, "rojo": 0.6, "verde": 0.5}

# Efecto día de semana (lunes=0 ... domingo=6).
WEEKDAY_FACTOR = [0.80, 0.80, 0.85, 0.90, 1.10, 1.40, 1.15]

PAYMENT_METHODS = ["tarjeta_credito", "tarjeta_debito", "efectivo", "billetera_digital"]
PAYMENT_WEIGHTS = [0.40, 0.30, 0.15, 0.15]

RETURN_RATE = 0.08
RETURN_REASONS = ["talla_incorrecta", "no_le_gusto", "defecto", "color_distinto"]
RETURN_REASON_WEIGHTS = [0.55, 0.25, 0.10, 0.10]
