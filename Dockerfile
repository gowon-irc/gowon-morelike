FROM python:3.10-slim AS build-env
# RUN apt-get update
# RUN apt-get install -y --no-install-recommends build-essential gcc

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py /opt/venv/bin

FROM python:3.10-slim
COPY --from=build-env /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"
CMD ["python", "-u", "/opt/venv/bin/main.py"]
