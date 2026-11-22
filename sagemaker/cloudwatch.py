"""Crea el grupo de logs, el dashboard `proyecto-ep3` y las alarmas en CloudWatch.

Adaptado de la guía del curso (herramientas/cloudwatch.py, capítulo 14). Se ejecuta en CloudShell:

    python3 sagemaker/cloudwatch.py

- Grupo de logs `/ity1102/proyecto` (retención 7 días): ahí escriben los contenedores con el driver awslogs.
- Dashboard `proyecto-ep3`: Invocations, ModelLatency y ModelSetupTime del endpoint, errores, CPU de la EC2
  y las últimas predicciones registradas por el dominio (buscables por `id`).
- Alarmas: errores 5XX del endpoint y CPU de la EC2 sobre 80 %.
"""
import json

import boto3

REGION = "us-east-1"
ENDPOINT = "nexo-recomendacion"
GRUPO_LOGS = "/ity1102/proyecto"
DASHBOARD = "proyecto-ep3"

logs = boto3.client("logs", region_name=REGION)
cw = boto3.client("cloudwatch", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)

try:
    logs.create_log_group(logGroupName=GRUPO_LOGS)
    print(f"Grupo de logs creado: {GRUPO_LOGS}")
except logs.exceptions.ResourceAlreadyExistsException:
    print(f"Grupo de logs ya existía: {GRUPO_LOGS}")
logs.put_retention_policy(logGroupName=GRUPO_LOGS, retentionInDays=7)

reservas = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": ["EC2-NexusRetail"]},
                                           {"Name": "instance-state-name", "Values": ["running", "stopped"]}])
instancias = [i["InstanceId"] for r in reservas["Reservations"] for i in r["Instances"]]
instancia = instancias[0] if instancias else None
print(f"Instancia EC2: {instancia}")

ep = ["AWS/SageMaker", None, "EndpointName", ENDPOINT, "VariantName", "principal"]


def metrica(nombre, estadistica, etiqueta):
    m = list(ep)
    m[1] = nombre
    return m + [{"stat": estadistica, "label": etiqueta}]


widgets = [
    {"type": "text", "x": 0, "y": 0, "width": 24, "height": 2, "properties": {"markdown":
        f"# Nexo · Equipo 2 · EP3\nEndpoint serverless **{ENDPOINT}** (2048 MB, concurrencia 10). "
        "ModelLatency y ModelSetupTime están en microsegundos."}},
    {"type": "metric", "x": 0, "y": 2, "width": 8, "height": 6, "properties": {
        "title": "Invocaciones del endpoint", "region": REGION, "view": "timeSeries", "period": 60,
        "metrics": [metrica("Invocations", "Sum", "Invocations")]}},
    {"type": "metric", "x": 8, "y": 2, "width": 8, "height": 6, "properties": {
        "title": "ModelLatency (µs)", "region": REGION, "view": "timeSeries", "period": 60,
        "metrics": [metrica("ModelLatency", "Average", "promedio"), metrica("ModelLatency", "p95", "p95")]}},
    {"type": "metric", "x": 16, "y": 2, "width": 8, "height": 6, "properties": {
        "title": "ModelSetupTime: cold start (µs)", "region": REGION, "view": "timeSeries", "period": 60,
        "metrics": [metrica("ModelSetupTime", "Maximum", "máximo"), metrica("ModelSetupTime", "Average", "promedio")]}},
    {"type": "metric", "x": 0, "y": 8, "width": 8, "height": 6, "properties": {
        "title": "Errores del endpoint", "region": REGION, "view": "timeSeries", "period": 60,
        "metrics": [metrica("Invocation4XXErrors", "Sum", "4XX"), metrica("Invocation5XXErrors", "Sum", "5XX")]}},
    {"type": "log", "x": 8, "y": 8, "width": 16, "height": 6, "properties": {
        "title": "Últimas predicciones (dominio)", "region": REGION,
        "query": f"SOURCE '{GRUPO_LOGS}' | fields @timestamp, @message "
                 "| filter @message like /prediccion/ | sort @timestamp desc | limit 20"}},
]
if instancia:
    widgets.append({"type": "metric", "x": 0, "y": 14, "width": 12, "height": 6, "properties": {
        "title": "CPU de la EC2 (%)", "region": REGION, "view": "timeSeries", "period": 300,
        "metrics": [["AWS/EC2", "CPUUtilization", "InstanceId", instancia, {"stat": "Average"}]]}})

cw.put_dashboard(DashboardName=DASHBOARD, DashboardBody=json.dumps({"widgets": widgets}))
print(f"Dashboard creado: {DASHBOARD}")

cw.put_metric_alarm(
    AlarmName="nexo-endpoint-errores-5xx", Namespace="AWS/SageMaker", MetricName="Invocation5XXErrors",
    Dimensions=[{"Name": "EndpointName", "Value": ENDPOINT}, {"Name": "VariantName", "Value": "principal"}],
    Statistic="Sum", Period=300, EvaluationPeriods=1, Threshold=1, ComparisonOperator="GreaterThanOrEqualToThreshold",
    TreatMissingData="notBreaching", AlarmDescription="El endpoint devolvió errores 5XX: el dominio usa la reserva")
if instancia:
    cw.put_metric_alarm(
        AlarmName="nexo-ec2-cpu-alta", Namespace="AWS/EC2", MetricName="CPUUtilization",
        Dimensions=[{"Name": "InstanceId", "Value": instancia}], Statistic="Average", Period=300,
        EvaluationPeriods=2, Threshold=80, ComparisonOperator="GreaterThanThreshold",
        TreatMissingData="notBreaching", AlarmDescription="CPU de la EC2 sobre 80 % por 10 minutos")
print("Alarmas creadas: nexo-endpoint-errores-5xx, nexo-ec2-cpu-alta")
print(f"\nLISTO. Abre: https://{REGION}.console.aws.amazon.com/cloudwatch/home?region={REGION}#dashboards/dashboard/{DASHBOARD}")
