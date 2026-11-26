"""Build the editable thesis results report from verified summary CSVs using bundled Python."""

import argparse
import json
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

NAMES = {'seasonal': 'Ingenuo estacional', 'random_forest': 'Random Forest', 'xgboost': 'XGBoost', 'lstm': 'LSTM'}
PROFILES = {'menu': 'Menú criollo', 'cevicheria': 'Cevichería', 'polleria': 'Pollería'}


def number(value, digits=2):
    if digits == 4 and not pd.isna(value) and 0 <= float(value) < .0001:
        return '<0,0001'
    return 'No definido' if pd.isna(value) else f'{float(value):,.{digits}f}'.replace(',', ' ').replace('.', ',')


def build(root):
    root = Path(root)
    summary = root/'resumen'
    def read(name):
        return pd.read_csv(summary/f'{name}.csv')
    info = json.loads((summary/'conclusiones_calculadas.json').read_text(encoding='utf-8'))
    if info['final_replications'] != 30 or info['pilot_replications'] != 5:
        raise ValueError('El informe definitivo requiere las treinta réplicas y los cinco pilotos completos')
    metrics, paired, total = read('metricas_por_modelo'), read('comparacion_politicas_por_insumo'), read('comparacion_politicas_total')
    selected, ablation, compare = read('metricas_modelo_seleccionado'), read('aporte_contexto'), read('comparacion_pronosticos')
    quality, inv = read('calidad_datasets'), read('inventario_total_por_replica')
    with zipfile.ZipFile(root/'final/results-2001.zip') as archive:
        environment = json.loads(archive.read('environment.json'))
    names = pd.read_csv(root/'configuracion/ingredients.csv').set_index('ingredient').name.to_dict()
    figures = root/'figuras'
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    labels = [NAMES[r.model]+(' con contexto' if r.external else ' sin contexto') if r.model != 'seasonal' else NAMES[r.model] for r in metrics.itertuples()]
    ax.barh(labels, metrics.wape_percent_mean, color=['#2c7a7b' if e else '#667eaa' for e in metrics.external])
    ax.set_xlabel('WAPE medio por serie y réplica (%)')
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(figures/'error_modelos.png', dpi=200)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3))
    for ax, key, label in zip(axes, ['waste_cost','stockout'], ['Vencimiento por réplica (S/)', 'Insumo días con quiebre'], strict=True):
        wide = inv.pivot(index='seed', columns='policy', values=key)
        for _, row in wide.iterrows():
            ax.plot([0,1], [row.empirical,row.forecast], color='#b2bdc9', alpha=.65)
        ax.plot([0,1], [wide.empirical.mean(),wide.forecast.mean()], color='#126e75', marker='o', lw=2.5)
        ax.set_xticks([0,1], ['Regla empírica', 'Pronóstico'])
        ax.set_ylabel(label)
    fig.tight_layout()
    fig.savefig(figures/'politicas_pareadas.png', dpi=200)
    plt.close(fig)

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin, section.bottom_margin = Inches(.75), Inches(.7)
    section.left_margin, section.right_margin = Inches(.85), Inches(.85)
    for style in ['Normal','Title','Subtitle','Heading 1','Heading 2','Caption']:
        s = doc.styles[style]
        s.font.name = 'Times New Roman'
        s.font.color.rgb = RGBColor(0,0,0)
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].paragraph_format.space_after = Pt(7)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.12
    doc.styles['Title'].font.size = Pt(23)
    doc.styles['Heading 1'].font.size = Pt(16)
    doc.styles['Heading 2'].font.size = Pt(12)
    header = section.header.paragraphs[0]
    header.text = 'GESTIÓN PREDICTIVA DE INSUMOS  |  RESULTADOS COMPUTACIONALES'
    header.runs[0].font.size = Pt(8)
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('26 de noviembre de 2026  •  Página ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    for run in footer.runs:
        run.font.size = Pt(8)

    def p(text):
        return doc.add_paragraph(text)

    def h(text, level=1, page=False):
        if page:
            doc.add_page_break()
        return doc.add_heading(text, level)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.autofit = False
        if widths is None:
            widths = [6.8/len(headers)]*len(headers)
        for cell, text in zip(t.rows[0].cells, headers, strict=True):
            cell.text = str(text)
        repeat = OxmlElement('w:tblHeader')
        t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            for cell, text in zip(t.add_row().cells, row, strict=True):
                cell.text = str(text)
        for i, row in enumerate(t.rows):
            trpr = row._tr.get_or_add_trPr()
            trpr.append(OxmlElement('w:cantSplit'))
            for j, cell in enumerate(row.cells):
                cell.width = Inches(widths[j])
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                tcpr = cell._tc.get_or_add_tcPr()
                borders = OxmlElement('w:tcBorders')
                for edge in ['top','left','bottom','right']:
                    tag = OxmlElement('w:'+edge)
                    for key, value in [('val','single'),('sz','4'),('color','D9D9D9')]:
                        tag.set(qn('w:'+key),value)
                    borders.append(tag)
                tcpr.append(borders)
                margins = OxmlElement('w:tcMar')
                for side in ['top','bottom','left','right']:
                    elem = OxmlElement('w:'+side)
                    elem.set(qn('w:w'),'90')
                    elem.set(qn('w:type'),'dxa')
                    margins.append(elem)
                tcpr.append(margins)
                shade = OxmlElement('w:shd')
                shade.set(qn('w:fill'), '334155' if i == 0 else ('F1F4F7' if i%2 == 0 else 'FFFFFF'))
                tcpr.append(shade)
                for para in cell.paragraphs:
                    para.paragraph_format.space_after = Pt(1)
                    para.paragraph_format.line_spacing = 1.04
                    para.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
                    for run in para.runs:
                        run.font.size = Pt(9.5)
                        run.bold = i == 0
                        run.font.color.rgb = RGBColor(255,255,255) if i == 0 else RGBColor(0,0,0)
        doc.add_paragraph().paragraph_format.space_after = Pt(1)
        return t

    def image(name, caption):
        doc.add_picture(str(figures/name), width=Inches(6.65))
        doc.add_paragraph(caption, style='Caption')

    doc.add_paragraph('Resultados de la simulación de demanda y compras de insumos', style='Title')
    doc.add_paragraph('Informe editable para integrar en la tesis', style='Subtitle')
    p('Se ejecutaron cinco réplicas piloto y treinta réplicas definitivas, con tres escenarios de restaurante por réplica. '
      'Los archivos conservan los datos generados, las predicciones, las decisiones de compra y los resultados diarios. '
      'La evidencia permite evaluar el comportamiento del software dentro de esta simulación; todavía no demuestra eficacia en restaurantes reales de Lima.')
    p(f'El modelo elegido exclusivamente en validación obtuvo un MAPE medio de {number(info["selected_mape_mean"])} % '
      f'y un WAPE medio de {number(info["selected_wape_mean"])} % en prueba. '
      f'{info["selected_series_mape_under20"]} de {info["selected_series_total"]} combinaciones de serie y réplica '
      'alcanzaron MAPE inferior al 20 %. Las comparaciones de merma y quiebres se presentan con sus intervalos y pruebas pareadas, incluidos resultados desfavorables.')
    total_index = total.set_index('indicator')
    waste_change = total_index.loc['expired','relative_reduction_percent']
    shortage_change = total_index.loc['stockout','relative_reduction_percent']
    p(f'Frente a la regla empírica, la cantidad vencida total {"disminuyó" if waste_change >= 0 else "aumentó"} '
      f'{number(abs(waste_change))} % y los insumo días con quiebre '
      f'{"disminuyeron" if shortage_change >= 0 else "aumentaron"} {number(abs(shortage_change))} %. '
      'Estos indicadores deben leerse juntos: atender más demanda puede elevar la merma y el gasto.')
    h('Alcance de los datos', 2)
    table(['Elemento','Contenido'], [
        ['Periodo por escenario','1 de enero de 2024 a 31 de diciembre de 2025'],
        ['Escenarios','Menú criollo, cevichería y pollería'],
        ['Cada réplica','9 platos, 24 series de insumo, 6 579 filas plato día y 17 544 filas insumo día'],
        ['Muestra definitiva','30 semillas; 90 historias de restaurante simuladas'],
        ['Unidad de réplica estadística','La semilla, n = 30; no los días ni los 90 escenarios'],
        ['Validación humana','V de Aiken y SUS pendientes de participantes reales'],
    ], [1.8,5.0])
    p('Los volúmenes, recetas, costos, plazos y vidas útiles son supuestos experimentales sin calibración empírica. '
      'Los feriados nacionales tienen fuentes documentales; la temperatura es una climatología sintética conocida. '
      'No se generaron opiniones de expertos ni respuestas de usuarios.')

    h('Diseño y reglas de generación', page=True)
    p('El protocolo se guardó antes de ejecutar los experimentos. Se usaron las semillas 1001 a 1005 para los pilotos y 2001 a 2030 '
      'para el análisis definitivo. Las treinta réplicas constituyen un presupuesto exploratorio fijado de antemano, '
      'sin cálculo de potencia ni garantía de significancia. No se eligieron semillas ni se ajustó el generador para alcanzar las hipótesis.')
    table(['Escenario','Platos y porciones base diarias','Atención'],[
        ['Menú criollo','Arroz con pollo 40; lentejas con bistec 25; estofado de pollo 20','Lunes a sábado'],
        ['Cevichería','Ceviche personal 35; arroz con mariscos 20; chicharrón de pescado 15','Todos los días'],
        ['Pollería','Cuarto de pollo 65; medio pollo 20; ensalada personal 15','Todos los días'],
    ],[1.2,4.0,1.6])
    p('La media diaria de cada plato combina sus porciones base, factores de fin de semana y feriado, un incremento supuesto '
      'del 5 % en los días 15, 30 y 31, y un efecto térmico en la cevichería. El ruido diario compartido por perfil es lognormal '
      'con sigma 0,18 y media unitaria. Con probabilidad 0,03 aparece un choque de factor 0,5 o 1,5. '
      'Las porciones son sorteos Poisson; los días cerrados tienen demanda cero.')
    p('La temperatura esperada sigue 21 + 4 cos[2π(día del año − 45)/365,25]. Su naturaleza periódica y conocida facilita '
      'la predicción respecto a clima real incierto. La necesidad cruda por insumo se calcula multiplicando '
      'las porciones solicitadas por la receta y sumando los platos que lo usan. Las solicitudes incluyen las no atendidas: '
      'no deben confundirse con ventas observadas cuando falta stock.')
    h('Control de calidad', 2)
    p(f'Los 35 archivos de datos pasaron los controles de unicidad, continuidad diaria, cantidades no negativas, '
      f'cierre sin demanda, regeneración por semilla y huellas SHA 256. Cada calendario contiene 32 feriados nacionales '
      f'en los dos años. El máximo error absoluto de balance de inventario fue {quality.mass_balance_max_error.max():.2e} kg. '
      'Se verificó stock inicial + recepciones = consumo atendido + vencimiento + saldo final, además de demanda = atendida + no atendida.')
    p('Cada escenario usa ocho insumos seleccionados. Las recetas son parciales: no representan todos los ingredientes '
      'necesarios para cocinar. Se registran 18 ingredientes distintos en el catálogo compartido. Todo se expresa en kg, '
      'incluido el aceite; sus costos también se refieren a kg. Esto evita mezclar unidades al sumar cantidades.')

    h('Evaluación temporal y selección de modelos', page=True)
    table(['Partición','Periodo','Días'],[
        ['Entrenamiento','2024 01 01 a 2025 05 31','517'],
        ['Validación','2025 06 01 a 2025 09 15','107'],
        ['Prueba reservada','2025 09 16 a 2025 12 31','107'],
    ],[1.7,4.2,.9])
    p('Se entrenó un modelo conjunto para las 24 series con identidad de perfil e insumo y escala calculada solo con el '
      'periodo de entrenamiento correspondiente. Las entradas contienen 14 rezagos y calendario conocido. La variante '
      'con contexto añade temperatura esperada, feriado y quincena. El modelo ingenuo usa la demanda de siete días atrás.')
    table(['Modelo','Configuraciones evaluadas','Entrenamiento'],[
        ['Random Forest','Profundidad 4 u 8; 70 árboles; mínimo 3 por hoja','Semilla 42; un hilo'],
        ['XGBoost','Profundidad 2 o 4; 90 árboles; tasa 0,06','Objetivo cuadrático; hist; un hilo'],
        ['LSTM','8 o 16 unidades; capa final de una salida','12 épocas; lotes 64; Adam 0,005'],
    ],[1.3,3.1,2.4])
    p('La selección minimiza el WAPE medio por serie en validación, tanto para el hiperparámetro como para el modelo '
      'ganador. Después se reentrena con entrenamiento y validación. La prueba se evalúa en bloques recursivos de hasta '
      'siete días: no se observa demanda interna del bloque. Entre bloques se incorpora el historial ya observado sin '
      'reentrenar el modelo. Para las compras se emite un horizonte diario, siempre con información anterior a la emisión.')
    p('MAE y RMSE se expresan en kg por insumo día. MAPE excluye los días con demanda cero, cuyo recuento se conserva '
      'en los CSV. WAPE divide error absoluto total entre demanda total de cada serie; R² puede ser negativo. '
      'Las tablas globales promedian primero las 24 series dentro de cada réplica y después las 30 réplicas; '
      'no son errores de una serie agregada de todos los productos.')
    p(f'Entorno de entrenamiento en CPU: Python {environment["python"]}, NumPy {environment["numpy"]}, '
      f'pandas {environment["pandas"]}, scikit learn {environment["scikit-learn"]}, '
      f'XGBoost {environment["xgboost"]}, TensorFlow {environment["tensorflow"]} y SciPy {environment["scipy"]}. '
      'Las dependencias completas se conservan en requirements-estudio.txt.')
    h('Frecuencia de selección en validación', 2)
    table(['Modelo','Contexto','Réplicas'], [[NAMES[r['model']], 'Sí' if r['external'] else 'No', r['count']] for r in info['winners']], [3.6,1.6,1.6])

    h('Resultados de precisión en prueba', page=True)
    table(['Modelo y contexto','MAE kg','RMSE kg','MAPE %','WAPE %','R²'],[
        [NAMES[r.model]+(' con' if r.external else ' sin') if r.model != 'seasonal' else NAMES[r.model],
         number(r.mae_mean),number(r.rmse_mean),number(r.mape_percent_mean),number(r.wape_percent_mean),number(r.r2_mean)]
        for r in metrics.itertuples()], [2.3,.9,.9,.9,.9,.9])
    p('Los promedios y las desviaciones entre semillas están disponibles en metricas_por_modelo.csv; '
      'metricas_por_serie.csv conserva cada combinación de perfil, insumo, modelo y semilla. '
      'Los resultados del modelo seleccionado no se sustituyen por los del modelo que mejor rindió en la prueba.')
    image('error_modelos.png','Figura 1  Error medio en las treinta réplicas definitivas. Menor WAPE indica menor error relativo.')
    h('Contraste frente al ingenuo',2)
    significant = compare[(compare.mean_reduction > 0) & (compare.p_holm_6_variants < .05)]
    p(f'{len(significant)} de las seis variantes de aprendizaje redujeron el WAPE frente al ingenuo con p ajustada '
      'por Holm inferior a 0,05. La inferencia se realiza sobre treinta diferencias pareadas por semilla mediante '
      'Wilcoxon bilateral. Los intervalos se obtienen con 3 000 remuestreos de semillas. Son comparaciones '
      'condicionadas a este generador, no una muestra de negocios peruanos.')

    h('Contrastes pareados de precisión', page=True)
    p('Se calcula para cada semilla el WAPE medio de sus 24 series y se compara con la referencia estacional '
      'de esa misma semilla. La mejora se expresa en puntos porcentuales de WAPE. Valores negativos indican '
      'que el modelo tiene mayor error que la referencia. La comparación de seis variantes utiliza ajuste Holm.')
    table(['Modelo y contexto','Mejora WAPE pp','IC 95 %','p Holm'],[
        [NAMES[r.model]+(' con' if r.external else ' sin'),number(r.mean_reduction),
         number(r.ci95_low)+' a '+number(r.ci95_high),number(r.p_holm_6_variants,4)]
        for r in compare.itertuples()], [2.5,1.25,1.8,1.25])
    chosen_compare = read('comparacion_modelo_seleccionado').iloc[0]
    p(f'La estrategia que selecciona el modelo en validación redujo el WAPE frente al ingenuo en '
      f'{number(chosen_compare.mean_reduction)} puntos porcentuales en promedio, con IC 95 % de '
      f'{number(chosen_compare.ci95_low)} a {number(chosen_compare.ci95_high)}. '
      f'Su p bilateral sin ajuste es {number(chosen_compare.p_value,4)}; se presenta como análisis '
      'complementario de la estrategia completa y no como un séptimo contraste confirmatorio independiente.')
    h('Cómo leer los intervalos y las pruebas',2)
    p('Se emplea Wilcoxon pareado bilateral entre semillas y un intervalo percentil de la media de la diferencia, '
      'obtenido mediante 3 000 remuestreos con reemplazo y semilla 42. El contraste de rangos y el intervalo de la '
      'media evalúan aspectos diferentes de la distribución: pueden no coincidir exactamente. '
      'Las filas con diferencias nulas reciben p = 1. Los intervalos no están ajustados por comparaciones múltiples.')
    p('En inventario, una diferencia positiva también indica mejora porque se resta pronóstico de empírica. '
      'La reducción relativa se calcula como la diferencia de medias dividida por la media empírica, multiplicada '
      'por cien; no es la media de treinta porcentajes. Si la media empírica es cero, el porcentaje no está definido. '
      'La magnitud absoluta y su intervalo deben acompañar cualquier afirmación basada en el umbral del 10 %.')

    h('Aporte del contexto y estabilidad', page=True)
    p('Para cada algoritmo se resta el WAPE con contexto al WAPE sin contexto dentro de la misma réplica. '
      'Un valor positivo indica mejora. Esta comparación incluye el reajuste del hiperparámetro en validación en cada variante, '
      'por lo que estima el aporte de la estrategia completa con contexto y no un efecto causal aislado de cada variable.')
    table(['Modelo','Mejora WAPE pp','IC 95 % de la mejora','p Holm'],[
        [NAMES[r.model],number(r.mean_reduction),number(r.ci95_low)+' a '+number(r.ci95_high),number(r.p_holm_3_models,4)]
        for r in ablation.itertuples()], [1.6,1.4,2.6,1.2])
    p('El ajuste Holm controla las tres comparaciones de contexto. Los intervalos son percentiles bootstrap de la media '
      'pareada y no se han ajustado por multiplicidad. El signo de la mejora y el intervalo deben leerse junto con la '
      'p ajustada. No se presupone que añadir contexto siempre mejore el pronóstico.')
    h('Modelo seleccionado por perfil',2)
    profile_selected = selected.groupby(['seed','profile'])[['mae','rmse','mape_percent','wape_percent','r2']].mean().groupby('profile').mean()
    table(['Perfil','MAE kg','RMSE kg','MAPE %','WAPE %','R²'],[
        [PROFILES[key],number(row.mae),number(row.rmse),number(row.mape_percent),number(row.wape_percent),number(row.r2)]
        for key,row in profile_selected.iterrows()], [2.3,.9,.9,.9,.9,.9])
    p(f'El promedio macro de MAPE del modelo seleccionado fue inferior al 20 % en {info["seeds_macro_mape_under20"]} '
      'de las treinta réplicas. Este recuento describe estabilidad entre simulaciones; no implica que todos los insumos '
      'cumplan el umbral. Los cierres dominicales del menú se excluyen del denominador de MAPE pero se conservan para MAE, RMSE y WAPE.')
    p('El archivo metricas_por_bloque.csv permite estudiar los bloques temporales sin tratarlos como observaciones '
      'independientes para las pruebas entre réplicas. Los contrastes Diebold Mariano aproximados por serie se conservan '
      'en los ZIP originales como análisis exploratorio, sin corrección conjunta; no se usan para declarar cumplimiento de hipótesis.')

    h('Simulación de compras e inventario', page=True)
    p('Se comparó una regla empírica supuesta basada en la media de jornadas abiertas de los 28 días anteriores '
      'con una regla que usa el pronóstico seleccionado. Ambas comparten solicitudes, costos, presentaciones, '
      'vida útil, plazos y stock inicial. El stock inicial equivale a un día de media histórica; la reserva adicional es 0,2 días. '
      'Ninguna de estas reglas fue obtenida mediante observación de restaurantes.')
    p('Cada día se retiran lotes vencidos, se proyecta el saldo hasta la entrega, se ordena en múltiplos de presentación, '
      'se reciben entregas debidas y se consume primero lo que vence antes. Los lotes conservan vida útil completa al '
      'recibirse. No hay compras urgentes ni entregas fuera del periodo de prueba; el saldo final no se fuerza a merma.')
    table(['Indicador por réplica','Empírica','Pronóstico','Reducción %','IC 95 % diferencia'],[
        [label,number(total.set_index('indicator').loc[key,'empirical_mean']),number(total.set_index('indicator').loc[key,'forecast_mean']),
         number(total.set_index('indicator').loc[key,'relative_reduction_percent']),
         number(total.set_index('indicator').loc[key,'ci95_low'])+' a '+number(total.set_index('indicator').loc[key,'ci95_high'])]
        for key,label in [('expired','Vencido kg'),('waste_cost','Vencido S/'),('stockout','Insumo días con quiebre'),('unmet','No atendido kg'),('purchase_cost','Compras S/')]],
        [2.1,1.05,1.05,1.0,1.7])
    image('politicas_pareadas.png','Figura 2  Cada línea representa una semilla; la línea oscura muestra la media. Diferencia = empírica menos pronóstico.')
    p('La cantidad vencida por insumo es el indicador primario. Las sumas de masa y costo son complementarias '
      'y no sustituyen el detalle. Un quiebre es un insumo día con cantidad no atendida; no equivale a un cliente perdido '
      'ni a un plato completo no servido. Una reducción negativa indica empeoramiento.')

    for profile in ['menu','cevicheria','polleria']:
        h('Merma y disponibilidad en '+PROFILES[profile], page=True)
        waste = paired[(paired.profile == profile) & (paired.indicator == 'expired')].set_index('ingredient')
        stock = paired[(paired.profile == profile) & (paired.indicator == 'stockout')].set_index('ingredient')
        p('Promedios de treinta semillas pareadas durante los 107 días de prueba. Merma significa vencimiento '
          'de insumo crudo. Las p se ajustan por Holm dentro de cada indicador, considerando las 24 series de los tres perfiles.')
        table(['Insumo','Vencido empírico kg','Vencido pronóstico kg','Reducción %','p Holm'],[
            [names[key],number(row.empirical_mean),number(row.forecast_mean),number(row.relative_reduction_percent),number(row.p_holm_24_series,4)]
            for key,row in waste.iterrows()], [1.6,1.4,1.4,1.2,1.3])
        h('Insumo días con quiebre',2)
        table(['Insumo','Empírica','Pronóstico','Reducción %','p Holm'],[
            [names[key],number(row.empirical_mean),number(row.forecast_mean),number(row.relative_reduction_percent),number(row.p_holm_24_series,4)]
            for key,row in stock.iterrows()], [1.6,1.4,1.4,1.2,1.3])
        p('Si la merma de referencia es cero, la reducción relativa no está definida; no se informa como 100 % '
          'ni como prueba de mejora. El CSV comparacion_politicas_por_insumo.csv incluye los intervalos de la '
          'diferencia absoluta, cantidad no atendida, costo vencido, tamaños de efecto y p sin ajustar.')

    h('Evaluación de las hipótesis de la tesis', page=True)
    p('La lectura de las hipótesis corresponde al informe proporcionado por los autores, página 9. '
      'Los siguientes resultados completan el componente computacional y delimitan lo que aún necesita evidencia externa.')
    h('HE1 Verosimilitud de los datos',2)
    p('Pendiente. El generador incorpora calendario y coherencia aritmética, pero todavía no está calibrado con '
      'ventas o resúmenes reales ni evaluado por tres expertos. No se puede afirmar V de Aiken ≥ 0,80. '
      'Debe describirse como datos sintéticos construidos mediante supuestos explícitos hasta completar esa validación.')
    h('HE2 Precisión y variables externas',2)
    best = metrics.loc[metrics.mape_percent_mean.idxmin()]
    p(f'El menor MAPE macro medio fue {number(best.mape_percent_mean)} %, con {NAMES[best.model]} '
      f'{"con" if best.external else "sin"} contexto. El criterio MAPE < 20 % '
      f'{"se alcanzó en el promedio de esa variante" if best.mape_percent_mean < 20 else "no se alcanzó en el promedio de ninguna variante"}. '
      f'{len(significant)} variantes superaron al ingenuo en WAPE con p Holm < 0,05. '
      'El aporte del contexto debe juzgarse por algoritmo en su tabla; alcanzar uno de los componentes no confirma automáticamente toda HE2.')
    h('HE3 Merma y quiebres',2)
    w = paired[paired.indicator == 'expired']
    s = paired[paired.indicator == 'stockout']
    good_w = set(zip(w.loc[(w.relative_reduction_percent >= 10) & (w.p_holm_24_series < .05),'profile'],w.loc[(w.relative_reduction_percent >= 10) & (w.p_holm_24_series < .05),'ingredient'],strict=True))
    good_s = set(zip(s.loc[(s.mean_paired_reduction > 0) & (s.p_holm_24_series < .05),'profile'],s.loc[(s.mean_paired_reduction > 0) & (s.p_holm_24_series < .05),'ingredient'],strict=True))
    p(f'{len(good_w)} de 24 series registraron reducción de vencimiento ≥ 10 % y p Holm < 0,05; '
      f'{len(good_s)} de 24 registraron menos quiebres con p Holm < 0,05. '
      f'Ambos criterios coincidieron en {len(good_w & good_s)} series. Estos recuentos no autorizan una afirmación '
      'universal sobre restaurantes. La política de referencia y las vidas útiles siguen pendientes de validación externa.')
    h('HE4 Usabilidad',2)
    p('Pendiente. El prototipo permite consultar datos y resultados, pero sus pruebas automatizadas no miden SUS. '
      'Se requieren respuestas reales de al menos cinco administradores y calcular el puntaje según el instrumento. '
      'No se atribuye SUS ≥ 68 sin esa evaluación.')

    h('Discusión y límites de interpretación', page=True)
    p('Las semillas replican el azar de un único conjunto de reglas. Su repetición mide estabilidad computacional '
      'bajo esos supuestos, no heterogeneidad de restaurantes reales. Las recetas de un mismo perfil comparten '
      'ruido y producen insumos correlacionados. Por esa razón los contrastes usan la semilla y no los días como réplicas independientes.')
    p('No se incluyeron crecimiento sostenido del negocio, cambios de carta, campañas comerciales, turismo, '
      'huelgas ni escenarios separados de inflación o desabastecimiento. Los choques aleatorios no sustituyen '
      'esos contextos. Esos fenómenos requieren datos y reglas propias en un estudio de sensibilidad posterior.')
    p('La climatología suave y conocida, las recetas constantes, el menú reducido y la observación completa de solicitudes '
      'simplifican la predicción. Un restaurante real suele registrar ventas limitadas por stock, promociones cambiantes, '
      'sustituciones, errores de captura y demanda no registrada. El desempeño observado no debe extrapolarse sin una '
      'prueba con registros reales y una evaluación temporal nueva.')
    p('Los resultados corresponden al módulo Investigación y a su simulador. El Plan de compras operativo utiliza '
      'su propio selector de Random Forest, referencia semanal o promedio según el historial disponible; '
      'no incorpora automáticamente el XGBoost o la LSTM ganadora de este estudio. Tampoco se transfieren '
      'los inventarios simulados a la base operativa. Validar esa integración constituye una tarea adicional '
      'antes de atribuir estos efectos al uso diario del prototipo.')
    p('Las vidas útiles presuponen conservación adecuada y los precios son constantes y supuestos; no constituyen '
      'recomendaciones de inocuidad ni precios medidos de mercado. Las presentaciones de compra, plazos y política '
      'empírica afectan fuertemente la merma. No se modelan capacidad de frío, presupuesto, compras mínimas del proveedor, '
      'escasez de mercado ni descarte de comida ya preparada.')
    p('El control Holm reduce falsas declaraciones al realizar múltiples contrastes; los intervalos bootstrap individuales '
      'son exploratorios. Treinta semillas no justifican por sí solas potencia suficiente. Las p muy pequeñas reflejan '
      'regularidad del efecto bajo el generador y no mayor representatividad peruana. El umbral 10 % y el umbral MAPE 20 % '
      'proceden de las hipótesis, sin reinterpretarse después de ver los datos.')
    h('Cambios necesarios en el informe de investigación',2)
    p('Precisar en metodología que esta etapa utiliza un generador no calibrado y distinguirla de la validación futura. '
      'Incorporar el protocolo temporal, las semillas y las unidades; definir quiebre como insumo día y merma como vencimiento '
      'de insumo crudo. Identificar la política empírica como una regla de comparación supuesta. '
      'En resultados, conservar los efectos desfavorables y los indicadores no definidos.')
    p('Añadir las tablas y figuras verificadas de este informe al capítulo de resultados. Mantener HE1 y HE4 pendientes '
      'hasta contar con valoraciones humanas. Si la tesis exige datos calibrados antes de comparar modelos, estas '
      'ejecuciones deben presentarse como estudio preliminar y repetirse tras calibrar y congelar un protocolo nuevo.')
    p('Para una siguiente evaluación, conviene elegir la reserva y la política de pedidos en validación según un '
      'costo conjunto de vencimiento y demanda no atendida, con valoración de faltantes obtenida del restaurante. '
      'Ese cambio requiere un protocolo nuevo y una prueba temporal nueva; no debe ajustarse usando los resultados '
      'finales de este estudio para después presentar el mismo periodo como prueba independiente.')

    h('Cómo volver a cargar y repetir el estudio', page=True)
    p('Para revisar un ejemplo se eligió la semilla 2001 por ser la primera réplica definitiva, sin seleccionar por su desempeño. '
      'El paquete contiene también las otras 29 réplicas definitivas y los cinco pilotos.')
    table(['Acción','Archivo o paso'],[
        ['Recargar datos','Investigación → 1 Dataset → Volver a cargar un dataset de investigación → dataset-2001.zip → Abrir dataset guardado'],
        ['Consultar resultados sin entrenar','Investigación → 2 Experimento → cargar results-2001.zip → Abrir resultados del experimento → 3 Resultados'],
        ['Archivos correctos','Usar dataset-2001.zip y results-2001.zip sin descomprimir ni renombrar su contenido'],
        ['Render gratuito','Permite revisar los archivos; el entrenamiento completo se realiza localmente'],
        ['CSV de investigación','profiles, recipes, ingredients, context, dish_demand y demand dentro de cada ZIP'],
        ['Datos operativos','Estos archivos pertenecen a Investigación; no cargarlos como ventas reales ni como compras en Configuración inicial'],
    ],[1.8,5.0])
    h('Reproducción local',2)
    p('Descomprimir paquete_reproducible.zip en una carpeta nueva y abrir PowerShell allí. Instalar Python 3.12 '
      'y ejecutar los pasos de LEEME.txt. El script secuencial permite reanudar: verifica archivos completos y '
      'se detiene si cambió el protocolo. Los resultados existentes no se sobrescriben al reanudar.')
    for command in ['py -3.12 -m venv .venv', '.venv\\Scripts\\python -m pip install -r requirements-estudio.txt',
        '.venv\\Scripts\\python -m pip install -e . --no-deps',
        '.venv\\Scripts\\python -m restaurante.research.study --output mi-repeticion',
        '.venv\\Scripts\\python scripts/summarize_study.py --output mi-repeticion']:
        q = p(command)
        for run in q.runs:
            run.font.name = 'Consolas'
            run.font.size = Pt(9)
    p('Las tablas generadas deben reproducirse con la misma semilla y versiones. Entrenamiento en CPU, bibliotecas '
      'y hardware distintos pueden introducir pequeñas diferencias numéricas; no se promete identidad binaria de '
      'los ZIP ni de las predicciones. Las huellas comprueban la integridad de los archivos entregados.')

    h('Parámetros de insumos y fuentes', page=True)
    ingredients = pd.read_csv(root/'configuracion/ingredients.csv')
    table(['Insumo','S por kg','Pack kg','Vida días','Plazo días'],[
        [r.name,number(r.cost),number(r.pack_size),r.shelf_life_days,r.lead_days] for r in ingredients.itertuples()], [2.3,1.1,1.1,1.1,1.2])
    p('Todos los parámetros de la tabla son supuestos sin calibración. Los coeficientes por plato están completos en '
      'configuracion/recipes.csv y en cada dataset. perfiles.csv no es el nombre de importación: se conserva profiles.csv '
      'para compatibilidad con la aplicación. El protocolo completo está en protocolo_congelado.json.')
    h('Fuentes y trazabilidad',2)
    p('Informe de investigación proporcionado por los autores: SISTEMAS GONZALO CACERES JOSEPH CHOMBO, '
      'versión adjunta de 35 páginas, especialmente objetivos e hipótesis en páginas 8 y 9. Documento en elaboración, sin resultados atribuidos.')
    p('El Peruano, calendario nacional 2024: https://elperuano.pe/noticia/238946-feriados-y-dias-no-laborables-en-peru-2024-revisa-aqui-los-dias-festivos-decretados-por-el-gobierno')
    p('El Peruano, calendario nacional 2025: https://www.elperuano.pe/noticia/261242-feriados-2025-en-peru-consulta-aqui-todos-los-dias-festivos-nacionales-y-organiza-tu-ano')
    p('Código de generación, evaluación y simulación incluido en el paquete reproducible. Las versiones, '
      'huellas de implementación y archivos de resultados permiten auditar cada cifra. La fecha del informe corresponde '
      'a su elaboración; el periodo de los datos simulados es 2024 a 2025.')
    output = root/'informe_resultados.docx'
    doc.save(output)
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/estudio-tesis-2026-11-26')
    build(parser.parse_args().output)
