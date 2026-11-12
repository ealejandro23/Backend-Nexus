#!/bin/sh
# Genera un certificado autofirmado si no existe y arranca Nginx.
# En producción se puede montar un certificado de Let's Encrypt en /etc/nginx/certs.
set -eu

mkdir -p /etc/nginx/certs

if [ ! -f /etc/nginx/certs/server.crt ] || [ ! -f /etc/nginx/certs/server.key ]; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout /etc/nginx/certs/server.key \
        -out /etc/nginx/certs/server.crt \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1" \
        >/dev/null 2>&1
fi

envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template \
    > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
