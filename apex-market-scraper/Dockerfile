FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apex_market_scraper ./apex_market_scraper
COPY configs ./configs
COPY README.md ./README.md

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "apex_market_scraper.cli", "--help"]
