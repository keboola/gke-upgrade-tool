FROM cgr.dev/chainguard/python:latest-dev as builder
WORKDIR /gke_upgrade_tool
COPY requirements.txt .
RUN pip install -r requirements.txt --user --no-cache-dir
FROM cgr.dev/chainguard/python:latest
WORKDIR /gke_upgrade_tool
COPY --from=builder /home/nonroot/.local/lib/python3.12/site-packages /home/nonroot/.local/lib/python3.12/site-packages
COPY main.py .
ENTRYPOINT [ "python", "/gke_upgrade_tool/main.py" ]
