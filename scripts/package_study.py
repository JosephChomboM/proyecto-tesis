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
    source = []
    for folder in ['src','scripts','tests','docs']:
        source.extend(path for path in (workspace/folder).rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix not in ['.pyc','.sqlite3'])
    source += [workspace/name for name in ['app.py','pyproject.toml','README.md','requirements.lock']]
    contents = [(path, path.relative_to(workspace).as_posix()) for path in source]
    allowed_folders = ['configuracion','pilot','final','resumen','figuras']
    for folder in allowed_folders:
        contents += [(path,'estudio/'+path.relative_to(root).as_posix()) for path in (root/folder).rglob('*') if path.is_file()]
    for name in ['protocolo_congelado.json','versiones.json','informe_resultados.docx']:
        contents.append((root/name,'estudio/'+name))
    contents += [(root/'LEEME.txt','LEEME.txt'),(root/'requirements-estudio.txt','requirements-estudio.txt')]
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
        archive.write(root/'LEEME.txt','LEEME.txt')
    print(root/'paquete_reproducible.zip')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/estudio-tesis-2026-11-26')
    package(parser.parse_args().output)
