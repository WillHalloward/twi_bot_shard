# Patreon API relay for the Twi Discord bot. Standard-library Python + curl.
FROM alpine:3.20
RUN apk add --no-cache python3 curl ca-certificates \
 && adduser -D -H -u 10001 relay
COPY relay.py /app/relay.py
USER relay
EXPOSE 8443
CMD ["python3", "-u", "/app/relay.py"]
