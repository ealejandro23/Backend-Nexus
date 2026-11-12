FROM nginx:1.27-alpine

RUN apk add --no-cache openssl gettext

COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DOMAIN=nexo.local

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-check-certificate -qO- https://localhost/healthz >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/entrypoint.sh"]
