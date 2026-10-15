# Dashboard image for the scrap and COPQ case (synthetic data included in the repository).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY scrap_copq/ scrap_copq/
COPY data/ data/
COPY reports/ reports/
COPY .streamlit/ .streamlit/
COPY streamlit_app.py .
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')"
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
