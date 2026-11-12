#!/usr/bin/env bash
# Bootstrap manual para una instancia Amazon Linux 2023 (AWS Academy).
# El stack de CloudFormation ya ejecuta estos pasos vía UserData.
set -euxo pipefail

dnf install -y docker git awscli
systemctl enable --now docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

mkdir -p /opt/nexo
chown ec2-user:ec2-user /opt/nexo

docker version
docker compose version
echo "Bootstrap Nexo EP3 OK"
