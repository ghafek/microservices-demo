
FROM python:3.12.12-alpine@sha256:d82291d418d5c47f267708393e40599ae836f2260b0519dd38670e9d281657f5 AS base

FROM base AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk update \
	&& apk add --no-cache g++ linux-headers \
	&& rm -rf /var/cache/apk/*

COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk update \
	&& apk add --no-cache libstdc++ \
	&& rm -rf /var/cache/apk/*

WORKDIR /ordertrackingservice

COPY --from=builder /usr/local/lib/python3.12/ /usr/local/lib/python3.12/

COPY . .

ENV PORT="8080"
EXPOSE 8080

ENTRYPOINT ["python", "order_tracking_server.py"]

