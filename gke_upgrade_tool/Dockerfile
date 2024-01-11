FROM cgr.dev/chainguard/python:latest-dev
WORKDIR /gke_upgrade_tool
COPY requirements.txt .
RUN pip install -r requirements.txt --user --no-cache-dir
COPY main.py .
ENTRYPOINT [ "python", "main.py" ]
