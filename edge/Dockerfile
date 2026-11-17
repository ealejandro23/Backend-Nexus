FROM caddy:2.10.0-alpine

# El Caddyfile viaja dentro de la imagen: deploy.sh sólo copia compose y .env
# a la EC2, así que un archivo montado desde el host no existiría allá.
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443

# Health por HTTP: /healthz se excluye de la redirección a HTTPS,
# por lo que no depende de que el certificado ya esté emitido.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1
