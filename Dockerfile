# Imagen del API y de la CLI de administracion.
#
# El panel se construye aparte, en despliegue/Dockerfile.panel: es estatico y lo
# sirve nginx, asi que Node no tiene por que viajar en esta imagen.

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# WeasyPrint genera el PDF desde HTML y necesita estas bibliotecas del sistema.
# Sin ellas la aplicacion arranca igual y solo falla al pedir un PDF, que es el
# peor momento para descubrirlo.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 \
      libcairo2 libgdk-pixbuf-2.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[api,postgres,salidas,programador,planos]"

COPY migraciones/ ./migraciones/
COPY herramientas/ ./herramientas/

# Usuario sin privilegios: si alguien logra ejecutar codigo, que no sea root.
RUN useradd --create-home --uid 10001 busint && chown -R busint /app
USER busint

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/salud',timeout=4)"

CMD ["uvicorn", "busint_alertas.arranque:app", "--host", "0.0.0.0", "--port", "8000"]
