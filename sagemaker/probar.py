"""Mide el cold start y la latencia en caliente del endpoint serverless (para el IE6).

    python3 sagemaker/probar.py            # 1.ª y 2.ª invocación + p50/p95 de 20 en caliente

Para ver el cold start, el endpoint tiene que llevar ~10 minutos sin uso.
"""
import statistics
import time

import boto3

REGION, ENDPOINT = "us-east-1", "nexo-recomendacion"
FILA = "2,0,0,59990,20,4,35000,34,1"
rt = boto3.client("sagemaker-runtime", region_name=REGION)


def invocar():
    inicio = time.perf_counter()
    r = rt.invoke_endpoint(EndpointName=ENDPOINT, ContentType="text/csv", Accept="text/csv", Body=FILA)
    r["Body"].read()
    return (time.perf_counter() - inicio) * 1000


primera, segunda = invocar(), invocar()
calientes = sorted(invocar() for _ in range(20))
print(f"1.ª invocación (posible cold start): {primera:.0f} ms")
print(f"2.ª invocación:                      {segunda:.0f} ms")
print(f"20 en caliente: p50 {statistics.median(calientes):.0f} ms · p95 {calientes[18]:.0f} ms")

cw = boto3.client("cloudwatch", region_name=REGION)
for metrica in ("ModelSetupTime", "ModelLatency"):
    datos = cw.get_metric_statistics(
        Namespace="AWS/SageMaker", MetricName=metrica,
        Dimensions=[{"Name": "EndpointName", "Value": ENDPOINT}, {"Name": "VariantName", "Value": "principal"}],
        StartTime=time.time() - 3 * 3600, EndTime=time.time(), Period=3600, Statistics=["Average", "Maximum"])
    puntos = datos.get("Datapoints", [])
    if puntos:
        p = max(puntos, key=lambda d: d["Timestamp"])
        print(f"CloudWatch {metrica}: promedio {p['Average'] / 1000:.1f} ms, máximo {p['Maximum'] / 1000:.1f} ms")
    else:
        print(f"CloudWatch {metrica}: sin datos aún (tarda unos minutos en aparecer)")
