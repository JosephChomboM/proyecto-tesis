"""National holidays for the thesis period, excluding compensable public-sector days."""

import pandas as pd

HOLIDAY_SOURCES = {
    2024: "https://elperuano.pe/noticia/238946-feriados-y-dias-no-laborables-en-peru-2024-revisa-aqui-los-dias-festivos-decretados-por-el-gobierno",
    2025: "https://www.elperuano.pe/noticia/261242-feriados-2025-en-peru-consulta-aqui-todos-los-dias-festivos-nacionales-y-organiza-tu-ano",
}


def national_holidays():
    fixed = {"01-01": "Año Nuevo", "05-01": "Día del Trabajo",
             "06-07": "Batalla de Arica y Día de la Bandera", "06-29": "San Pedro y San Pablo",
             "07-23": "Día de la Fuerza Aérea del Perú", "07-28": "Fiestas Patrias",
             "07-29": "Fiestas Patrias", "08-06": "Batalla de Junín",
             "08-30": "Santa Rosa de Lima", "10-08": "Combate de Angamos",
             "11-01": "Todos los Santos", "12-08": "Inmaculada Concepción",
             "12-09": "Batalla de Ayacucho", "12-25": "Navidad"}
    movable = {2024: {"03-28": "Jueves Santo", "03-29": "Viernes Santo"},
               2025: {"04-17": "Jueves Santo", "04-18": "Viernes Santo"}}
    return {pd.Timestamp(f"{year}-{day}"): name
            for year in HOLIDAY_SOURCES for day, name in (fixed | movable[year]).items()}
