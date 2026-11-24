"""Spanish names for the corruption kinds. The code identifiers stay as they are in the injector;
only the reader of the dashboard sees these labels."""

KIND_LABELS = {
    "nulls": "Precios nulos",
    "duplicates": "Filas duplicadas",
    "unit_error": "Error de unidad (todos los precios por 10)",
    "typo_zeros": "Ceros de más en algunos precios",
    "negative": "Precios negativos",
    "min_gt_max": "Mínimo mayor que el máximo",
    "bad_dates": "Fechas inválidas",
    "bad_category": "Categoría mal escrita",
}
