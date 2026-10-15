# Abstract Fetcher · UAGro

Aplicación de escritorio basada en el cuaderno de referencias de Iván Gallardo Bernal.
Permite cargar referencias, buscar resúmenes públicos y guardar una tabla CSV para Excel.

## Empezar en Windows

1. Extrae todo el ZIP en una carpeta de tu computadora. No ejecutes los archivos dentro del ZIP.
2. Si tienes Python 3.10 o posterior, haz doble clic en **ABRIR_APP.bat**.
3. Se abrirá la ventana. Comprueba tu correo de contacto.
4. Pulsa **Cargar Excel / CSV** y selecciona tus referencias.
5. Pulsa **Buscar resúmenes** y elige un nombre para el CSV de resultados.
6. Espera a que termine. Puedes seleccionar una fila para leer su resumen o abrir su enlace.

La aplicación solo usa módulos incluidos en Python; no requiere pandas ni Excel instalado.
En la instalación de Python para Windows incluye Tcl/Tk y marca **Add Python to PATH**.
Descarga oficial: https://www.python.org/downloads/windows/

## Crear el archivo .exe

El ZIP contiene el código y el generador: **no contiene un .exe ya compilado**.
La compilación y la comprobación final de Windows deben hacerse en una PC Windows.

1. En Windows, con Python 3.10 o posterior instalado, abre **CREAR_EXE_WINDOWS.bat**.
2. El archivo prepara un entorno aislado, descarga PyInstaller, ejecuta las pruebas y compila.
3. Al terminar abre la carpeta **dist**, donde estará **AbstractFetcher.exe**.
4. Abre ese archivo y prueba una búsqueda. Después puedes copiar únicamente el .exe
   a otro equipo Windows compatible. Ese equipo no necesita Python; sí necesita Internet
   para consultar las bases de datos.

La primera compilación necesita Internet. No requiere modificar manualmente el código.
Genera el ejecutable en una arquitectura de Windows compatible con el equipo de destino.
El programa y el ejecutable generado no tienen firma digital.

## Tu archivo de entrada

- Acepta **.xlsx** (primera hoja) o **.csv** (coma, punto y coma o tabulador).
- La primera fila debe contener encabezados únicos y no vacíos.
- Necesita una columna llamada **Title** o **Título**; las mayúsculas no importan.
- **Index** es opcional. Se conservan las demás columnas.
- Los títulos deben estar escritos como texto. Para fórmulas en Excel se utiliza el valor
  calculado guardado por Excel; guarda el libro después de calcularlo.
- Para archivos antiguos .xls, conviértelos primero a .xlsx.
- Incluimos **referencias_ejemplo.csv** para una primera prueba; sus resultados no vienen precargados.

## Cómo busca y qué guarda

Consulta PubMed, Crossref y Europe PMC en ese orden; si una fuente obtiene un resumen con
una coincidencia aceptada, pasa a la siguiente referencia. Semantic Scholar es opcional:
se activa escribiendo tu propia clave en la ventana. La clave no se guarda en archivos.
El correo de contacto se envía a los servicios junto con las consultas; los títulos se envían
a las bases consultadas. Los archivos de entrada y resultados permanecen en tu computadora.

Compara el título solicitado con hasta tres candidatos de cada consulta. Acepta una
similitud de texto de al menos 0.88. **Este número no es una probabilidad de acierto**:
revisa manualmente las coincidencias, en particular títulos cortos, versiones y traducciones.
No comprueba automáticamente autores ni años. Busca por título; no es un buscador por DOI.

El CSV conserva los campos de entrada y añade los siguientes campos de resultados:

| Campo | Contenido |
| --- | --- |
| Original_Title | Título utilizado para buscar |
| Matched_Title | Título recuperado de la fuente |
| DOI | DOI de ese registro, si está disponible |
| Abstract | Resumen recuperado; vacío si no se consiguió |
| Abstract_Source | Fuente del registro recuperado |
| URL | Enlace del registro |
| Match_Score | Similitud entre los títulos, de 0 a 1 |
| Status | Resumen recuperado, Sin resumen público, Sin coincidencia aceptada o Sin título |
| Query_Errors | Fuentes que fallaron durante la consulta |

Si la entrada ya tiene columnas con estos nombres, sus valores se sustituyen por el resultado
de esta búsqueda. La columna Title de entrada y el archivo original se conservan.
Un registro sin resumen no significa que el artículo no tenga resumen: puede no estar
expuesto por estas fuentes. Si hay errores de conexión, revisa Query_Errors y repite la búsqueda.
**No genera ni inventa resúmenes. No descarga el texto completo de los artículos.**

El CSV se guarda después de cada referencia terminada, en UTF-8 con BOM para Excel.
Si pulsas **Detener**, conserva lo terminado; una consulta activa puede tardar hasta
20 segundos antes de responder. Si cierras la aplicación mientras trabaja, primero solicita
detenerla; espera el aviso y luego cierra. Si falla el guardado, conserva los resultados
en pantalla y usa **Guardar copia CSV**. No mantengas abierto en Excel el archivo de salida
mientras se escribe. Volver a buscar empieza desde la primera referencia; no hay reanudación.
Los textos que empiezan con símbolos de fórmula se prefijan con un apóstrofo al exportar.

## Verificación y desarrollo

Desde esta carpeta:

```text
python -m unittest discover -s tests -v
python abstract_fetcher.py
```

Las pruebas usan respuestas de ejemplo para verificar lectores, limpieza, estructura de los
resúmenes, selección de coincidencias, incidencias, reintentos y cancelación sin depender de
servicios externos. La entrega pasó 20 pruebas en Linux. También se verificaron respuestas reales de PubMed,
Crossref y Europe PMC, y se recuperaron el resumen y el DOI de «A guide to deep learning
in healthcare» (10.1038/s41591-018-0316-z). El renderizado de la ventana y la compilación
.exe requieren verificación en Windows; no se ha probado un binario de Windows.

Documentación de las fuentes y empaquetado:
- NCBI E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- Crossref REST: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Europe PMC: https://europepmc.org/RestfulWebService
- PyInstaller: https://pyinstaller.org/en/stable/operating-mode.html
