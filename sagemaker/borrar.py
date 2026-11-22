"""Borra el endpoint serverless (y opcionalmente su configuración y modelo).

    python3 sagemaker/borrar.py           # solo el endpoint
    python3 sagemaker/borrar.py --todo    # endpoint, configuraciones y modelos nexo-*

Un endpoint serverless no cobra mientras no se invoca, pero conviene borrarlo al terminar el curso.
"""
import sys

import boto3

sm = boto3.client("sagemaker", region_name="us-east-1")
try:
    sm.delete_endpoint(EndpointName="nexo-recomendacion")
    print("Endpoint nexo-recomendacion borrado")
except sm.exceptions.ClientError as exc:
    print(f"Endpoint: {exc}")
if "--todo" in sys.argv:
    for c in sm.list_endpoint_configs(NameContains="nexo-config")["EndpointConfigs"]:
        sm.delete_endpoint_config(EndpointConfigName=c["EndpointConfigName"])
        print("Config borrada:", c["EndpointConfigName"])
    for m in sm.list_models(NameContains="nexo-modelo")["Models"]:
        sm.delete_model(ModelName=m["ModelName"])
        print("Modelo borrado:", m["ModelName"])
