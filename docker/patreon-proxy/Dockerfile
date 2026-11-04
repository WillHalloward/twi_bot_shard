# Minimal forward proxy so the Twi bot (on Railway) can reach Patreon from a
# residential IP. Built locally from Alpine's own tinyproxy package.
FROM alpine:3.20
RUN apk add --no-cache tinyproxy
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
