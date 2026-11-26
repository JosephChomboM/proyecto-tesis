"""Package verified study files and portable source without databases or secrets."""

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def package(root):
    root = Path(root).resolve()
    workspace = Path(__file__).resolve().parents[1]
    plan = json.loads((root/'protocolo_congelado.json').read_text(encoding='utf-8'))
    for phase, seeds in [('pilot',plan['pilot_seeds']),('final',plan['final_seeds'])]:
        for seed in seeds:
            complete = json.loads((root/phase/f'completed-{seed}.json').read_text(encoding='utf-8'))
            for prefix in ['dataset','results']:
                assert hashlib.sha256((root/phase/f'{prefix}-{seed}.zip').read_bytes()).hexdigest() == complete[prefix+'_sha256']
    assert (root/'informe_resultados.docx').exists()
    requirements = subprocess.check_output([sys.executable,'-m','pip','freeze','--exclude-editable'],text=True)
    if any(' @ file:' in line or line.startswith('-e ') for line in requirements.splitlines()):
        raise ValueError('Dependencia local no portable')
    (root/'requirements-estudio.txt').write_text(requirements,encoding='utf-8')
    (root/'versiones.json').write_text(json.dumps({name:importlib.metadata.version(name) for name in
        ['numpy','pandas','scikit-learn','tensorflow','xgboost','scipy']},indent=2),encoding='utf-8')
    guide = '''ESTUDIO COMPUTACIONAL DE DEMANDA Y COMPRAS DE INSUMOS

EMPEZAR SIN ENTRENAR
1. Abre la aplicación y entra en Investigación.
2. En 1 Dataset, expande Volver a cargar un dataset de investigación.
3. Carga estudio/final/dataset-2001.zip y pulsa Abrir dataset guardado.
4. En 2 Experimento carga estudio/final/results-2001.zip y pulsa Abrir resultados del experimento.
5. Consulta 3 Resultados. Puedes repetir con las semillas 2002 a 2030.
Usa los ZIP individuales sin descomprimirlos. No subas este paquete completo en esos controles.
La primera semilla se entrega como ejemplo por orden, no por mejor desempeño.

DATOS Y RESULTADOS
35 datasets: cinco pilotos (1001-1005) y treinta definitivos (2001-2030).
Cada dataset contiene profiles.csv, recipes.csv, ingredients.csv, context.csv,
dish_demand.csv, demand.csv y metadata.json. Cada uno corresponde a los tres perfiles.
Cada results-SEMILLA.zip guarda todos los modelos, predicciones e inventario diario.
Los pilotos quedan fuera de los contrastes definitivos. Los resumenes están en estudio/resumen.
Consulta estudio/informe_resultados.docx para interpretación, tablas y limitaciones.
No debes cargar compras, stock ni mermas por separado para este experimento: el simulador
los calcula con las mismas reglas iniciales para ambas políticas. El uso operativo del
restaurante tiene otros formularios y plantillas, separados de Investigación.

REPETIR TODO LOCALMENTE EN WINDOWS
Requiere Python 3.12 de 64 bits. Abre PowerShell en la carpeta descomprimida:
  py -3.12 -m venv .venv
  .venv\\Scripts\\python -m pip install -r requirements-estudio.txt
  .venv\\Scripts\\python -m pip install -e . --no-deps
  .venv\\Scripts\\python -m restaurante.research.study --output mi-repeticion
  .venv\\Scripts\\python scripts/summarize_study.py --output mi-repeticion
Para abrir la interfaz:
  .venv\\Scripts\\python -m streamlit run app.py
El entrenamiento tarda varios minutos por semilla y puede reanudarse con el mismo comando.
No edites la implementación científica tras iniciar una carpeta de estudio.
Para recalcular sin reutilizar los archivos entregados utiliza otra carpeta, como mi-repeticion.
No ejecutes dos lanzadores sobre las mismas semillas en la misma carpeta.
El ejecutor paralelo es opcional y solo procesa las semillas definitivas del protocolo ya congelado.

REPRODUCIBILIDAD
Las semillas fijan la generación de datos. El código y las versiones se incluyen para auditoría.
CPU, plataforma y bibliotecas pueden causar pequeñas diferencias numéricas de entrenamiento.
No se garantiza identidad binaria de archivos ZIP ni de predicciones entre equipos.
SHA256SUMS.txt verifica los archivos entregados; cada checkpoint guarda además sus dos huellas.
No cambies parámetros para buscar que las hipótesis se cumplan. Cualquier cambio corresponde
a un protocolo nuevo en otra carpeta y debe declararse en el informe.

ALCANCE
Son datos sintéticos de solicitudes, no ventas ni registros de restaurantes reales.
No cargarlos como operaciones reales en Configuración inicial. No constituyen calibración peruana.
Costos, recetas parciales, vidas útiles y política empírica son supuestos no validados.
Aiken y SUS quedan pendientes de expertos y administradores reales. No se inventaron respuestas.
Render continúa en modalidad gratuita; el experimento se ejecutó localmente.

El informe editable se entrega terminado con los resultados computacionales obtenidos.
La reconstrucción del DOCX es opcional: scripts/build_study_report.py requiere python-docx
y matplotlib en un entorno de documentos; no es necesaria para repetir los experimentos.
'''
    (root/'LEEME.txt').write_text(guide,encoding='utf-8-sig')
    dictionary = '''DICCIONARIO DE LOS DATASETS DE INVESTIGACION
Formato: CSV UTF-8 con BOM, separador coma, decimal punto y fechas AAAA-MM-DD.
Las columnas de días de semana contienen listas entre comillas cuando tienen comas.
Para recargar en la aplicación utiliza el ZIP individual completo y sin editar.

profiles.csv: una fila por plato (9 filas).
profile: código del escenario, menu, cevicheria o polleria; no es un restaurante real.
restaurant: nombre descriptivo del perfil. dish: identificador único del plato.
daily_portions: porciones base diarias, antes de calendario y ruido.
weekdays: días abiertos, 0 lunes a 6 domingo.
weekend_factor y holiday_factor: multiplicadores supuestos de la media.
heat_effect: incremento relativo por grado sobre 21 grados Celsius.
source: supuesto o fuente de los parámetros; en este estudio no calibrados.

recipes.csv: una fila por plato e insumo seleccionado (53 filas).
dish, ingredient: enlaces a los catálogos. quantity: kg crudos por porción solicitada.
source: procedencia declarada. Las recetas son parciales, limitadas a insumos seleccionados.

ingredients.csv: catálogo compartido de 18 ingredientes distintos.
ingredient: código único. name: nombre visible. unit: kg en todo el estudio.
cost: soles supuestos por kg. pack_size: múltiplo de compra en kg.
shelf_life_days: vida útil supuesta completa al recibir el lote, bajo conservación adecuada.
lead_days: días de plazo entre pedido y recepción; 0 significa entrega el mismo día.
source: supuesto de este estudio. El aceite se expresa en kg y su costo es por kg.

context.csv: una fila por fecha, 731 filas.
date: fecha. expected_temperature: climatología sintética conocida, no medición futura.
holiday: 1 feriado nacional, 0 otro día. context_source: fuente o supuesto explícito.
payday: indicador supuesto de los días 15, 30 y 31; no pagos reales observados.
Los feriados no equivalen a cierre; cada perfil mantiene su calendario de apertura.

dish_demand.csv: una fila por fecha, perfil y plato, 6 579 filas.
date, profile, dish: clave conjunta. is_open: True/False según calendario del perfil.
demand_portions: solicitudes potenciales simuladas; incluye lo no atendido por falta de stock.
No son comprobantes de venta ni conteos observados en un restaurante.

demand.csv: una fila por fecha, perfil e insumo, 17 544 filas.
date, profile, ingredient: clave conjunta de 24 series de 731 días.
demand: kg necesarios = suma de porciones solicitadas por cantidad cruda de receta.
expected_temperature, holiday, context_source, payday: contexto de esa fecha.
is_open: atención del perfil; un cierre tiene demanda cero explícita.
Los ceros son cierres conocidos; no se sustituyen registros faltantes por cero.

metadata.json: configuración de generación, semilla, supuestos, fuentes y huellas.
sources_validated=False y experts_completed=False: calibración y juicio de expertos pendientes.
No modificar un CSV ni la semilla para buscar un resultado favorable. Para un escenario
nuevo, editar las tablas de configuración y generar otro dataset con protocolo nuevo.

RESULTADOS
metrics.csv: error por serie, modelo y contexto; MAE/RMSE/sesgo en kg, MAPE/WAPE en porcentaje.
MAPE excluye ceros e informa su cantidad; R2 indefinido o negativo se conserva.
predictions.csv: valores solicitados y pronosticados por fecha y origen de bloque.
decision_predictions.csv: horizontes emitidos diariamente para simular las compras.
model_status.csv y tuning.csv: configuraciones y resultados de validación; no selección en prueba.
inventory_daily.csv: pedidos, recepciones, consumo atendido, no atendido, vencido y saldo por día y política.
stockout cuenta insumo días con demanda no atendida; no clientes ni platos completos.
inventory_summary.csv: totales por perfil, ingrediente y política, con stock inicial y final.
policy empirical: media de días abiertos en los 28 días previos; policy forecast: modelo seleccionado.
inventory_protocol.json y experiment.json: reglas y selección efectivamente utilizadas.
Los resúmenes finales agregan solo semillas 2001-2030; cada semilla es una réplica pareada.
'''
    (root/'DICCIONARIO_DATOS.txt').write_text(dictionary,encoding='utf-8-sig')
    source = []
    for folder in ['src','scripts','tests','docs']:
        source.extend(path for path in (workspace/folder).rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.sqlite3'])
    source += [workspace/name for name in ['app.py','pyproject.toml','README.md','requirements.lock',
        '.python-version','.streamlit/config.toml']]
    contents = [(path, path.relative_to(workspace).as_posix()) for path in source]
    allowed_folders = ['configuracion','pilot','final','resumen','figuras']
    for folder in allowed_folders:
        contents += [(path,'estudio/'+path.relative_to(root).as_posix()) for path in (root/folder).rglob('*') if path.is_file()]
    for name in ['protocolo_congelado.json','versiones.json','informe_resultados.docx']:
        contents.append((root/name,'estudio/'+name))
    contents += [(root/'LEEME.txt','LEEME.txt'),(root/'DICCIONARIO_DATOS.txt','DICCIONARIO_DATOS.txt'),
        (root/'requirements-estudio.txt','requirements-estudio.txt')]
    checksums = '\n'.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name for path,name in sorted(contents,key=lambda item:item[1]))+'\n'
    (root/'SHA256SUMS.txt').write_text(checksums,encoding='utf-8')
    with zipfile.ZipFile(root/'paquete_reproducible.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path,name in contents:
            archive.write(path,name)
        archive.write(root/'SHA256SUMS.txt','SHA256SUMS.txt')
    with zipfile.ZipFile(root/'todos_los_datasets.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for phase in ['pilot','final']:
            for path in sorted((root/phase).glob('dataset-*.zip')):
                archive.write(path,phase+'/'+path.name)
        archive.write(root/'DICCIONARIO_DATOS.txt','DICCIONARIO_DATOS.txt')
        archive.writestr('EMPEZAR.txt',
            'Este paquete contiene solo los 35 datasets. Descomprime este ZIP general.\n'
            'En Investigacion, pestana 1 Dataset, abre Volver a cargar un dataset de investigacion.\n'
            'Carga final/dataset-2001.zip sin descomprimir ese ZIP individual y pulsa Abrir dataset guardado.\n'
            'Puedes usar las semillas 2002 a 2030; pilot contiene los cinco pilotos excluidos del analisis final.\n'
            'No cargues el ZIP general en la aplicacion ni importes estas solicitudes como ventas reales.\n'
            'Los resultados ya entrenados, el informe y las instrucciones completas estan en paquete_reproducible.zip.\n')
    print(root/'paquete_reproducible.zip')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/estudio-tesis-2026-11-26')
    package(parser.parse_args().output)
