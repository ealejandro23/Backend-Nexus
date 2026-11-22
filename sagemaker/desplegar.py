"""Entrena el modelo de propensión en SageMaker y lo publica en un endpoint SERVERLESS.

Adaptado de la guía del curso (github.com/Umbingelelo/ity1102-guia-proyecto, capítulo 11 y sagemaker/*).
Se ejecuta en AWS CloudShell (usa las credenciales del Learner Lab y el rol LabRole).

    git clone https://github.com/ealejandro23/Backend-Nexus.git && cd Backend-Nexus
    python3 sagemaker/desplegar.py

Pasos: (1) datos tratados con datos/preparar.py, (2) CSV para XGBoost, (3) subida a S3,
(4) training job con el XGBoost integrado de SageMaker, (5) endpoint serverless, (6) prueba.
Al terminar imprime ENDPOINT_MODELO para el .env del servidor.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

import boto3

REGION = "us-east-1"
CASO = "recomendacion"
ENDPOINT = "nexo-recomendacion"
IMAGEN_XGBOOST = "683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.7-1"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRATADOS = os.path.join(RAIZ, "datos", "datos_tratados")
CRUDOS = os.path.join(RAIZ, "datos", "crudos")
CRUDOS_URL = "https://raw.githubusercontent.com/ealejandro23/Microservicio-IA/main/datos/crudos/{}.csv"
ESTADO = os.path.join(RAIZ, "sagemaker", "estado.json")


def paso(texto):
    print(f"\n==> {texto}", flush=True)


def preparar_datos():
    if os.path.exists(os.path.join(TRATADOS, "X_train.csv")):
        return
    paso("Preparando datos (datos/preparar.py)")
    os.makedirs(CRUDOS, exist_ok=True)
    for nombre in ("productos", "usuarios", "transacciones", "clickstream"):
        destino = os.path.join(CRUDOS, f"{nombre}.csv")
        if not os.path.exists(destino):
            urllib.request.urlretrieve(CRUDOS_URL.format(nombre), destino)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                           "pandas", "numpy", "scikit-learn", "joblib"])
    subprocess.check_call([sys.executable, os.path.join(RAIZ, "datos", "preparar.py")])


def csv_xgboost():
    """XGBoost integrado: etiqueta en la primera columna, sin encabezado."""
    import pandas as pd

    columnas = json.load(open(os.path.join(TRATADOS, "feature_cols.json"), encoding="utf-8"))
    salidas = {}
    for parte, nombre in (("train", "train"), ("test", "validation")):
        x = pd.read_csv(os.path.join(TRATADOS, f"X_{parte}.csv"))[columnas]
        y = pd.read_csv(os.path.join(TRATADOS, f"y_{parte}.csv")).iloc[:, 0]
        ruta = os.path.join(TRATADOS, f"xgb_{nombre}.csv")
        pd.concat([y.astype(int), x], axis=1).to_csv(ruta, header=False, index=False)
        salidas[nombre] = ruta
    print(f"   columnas: {columnas}")
    return columnas, salidas


def esperar(funcion, campo, listo, fallo, cada=15):
    while True:
        estado = funcion()[campo]
        print(f"   {campo}: {estado}", flush=True)
        if estado in listo:
            return estado
        if estado in fallo:
            raise SystemExit(f"Falló: {estado}")
        time.sleep(cada)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memoria", type=int, default=2048, help="MB del endpoint serverless")
    parser.add_argument("--concurrencia", type=int, default=10, help="MaxConcurrency del endpoint")
    args = parser.parse_args()

    cuenta = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    rol = f"arn:aws:iam::{cuenta}:role/LabRole"
    bucket = f"ity1102-ep3-{cuenta}"
    s3 = boto3.client("s3", region_name=REGION)
    sm = boto3.client("sagemaker", region_name=REGION)
    sufijo = time.strftime("%Y%m%d-%H%M%S")

    preparar_datos()
    paso("Generando CSV para XGBoost")
    columnas, archivos = csv_xgboost()

    paso(f"Subiendo a s3://{bucket}/{CASO}/")
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)
    for nombre, ruta in archivos.items():
        s3.upload_file(ruta, bucket, f"{CASO}/{nombre}/{nombre}.csv")

    paso("Entrenando con el XGBoost integrado de SageMaker (2 a 5 min)")
    trabajo = f"nexo-xgb-{sufijo}"
    sm.create_training_job(
        TrainingJobName=trabajo,
        AlgorithmSpecification={"TrainingImage": IMAGEN_XGBOOST, "TrainingInputMode": "File"},
        RoleArn=rol,
        InputDataConfig=[
            {"ChannelName": canal, "ContentType": "text/csv",
             "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3DataDistributionType": "FullyReplicated",
                                             "S3Uri": f"s3://{bucket}/{CASO}/{canal}/"}}}
            for canal in ("train", "validation")
        ],
        OutputDataConfig={"S3OutputPath": f"s3://{bucket}/{CASO}/modelos/"},
        ResourceConfig={"InstanceType": "ml.m5.large", "InstanceCount": 1, "VolumeSizeInGB": 5},
        StoppingCondition={"MaxRuntimeInSeconds": 1200},
        HyperParameters={"objective": "binary:logistic", "eval_metric": "aucpr", "num_round": "200",
                         "max_depth": "3", "eta": "0.05", "subsample": "0.8", "min_child_weight": "50"},
    )
    esperar(lambda: sm.describe_training_job(TrainingJobName=trabajo), "TrainingJobStatus",
            {"Completed"}, {"Failed", "Stopped"}, cada=30)
    artefacto = sm.describe_training_job(TrainingJobName=trabajo)["ModelArtifacts"]["S3ModelArtifacts"]

    paso(f"Creando endpoint serverless {ENDPOINT} ({args.memoria} MB, concurrencia {args.concurrencia})")
    modelo = f"nexo-modelo-{sufijo}"
    config = f"nexo-config-{sufijo}"
    sm.create_model(ModelName=modelo, ExecutionRoleArn=rol,
                    PrimaryContainer={"Image": IMAGEN_XGBOOST, "ModelDataUrl": artefacto})
    sm.create_endpoint_config(EndpointConfigName=config, ProductionVariants=[{
        "VariantName": "principal", "ModelName": modelo,
        "ServerlessConfig": {"MemorySizeInMB": args.memoria, "MaxConcurrency": args.concurrencia}}])
    try:
        sm.describe_endpoint(EndpointName=ENDPOINT)
        sm.update_endpoint(EndpointName=ENDPOINT, EndpointConfigName=config)
    except sm.exceptions.ClientError:
        sm.create_endpoint(EndpointName=ENDPOINT, EndpointConfigName=config)
    esperar(lambda: sm.describe_endpoint(EndpointName=ENDPOINT), "EndpointStatus",
            {"InService"}, {"Failed"}, cada=20)

    paso("Probando el endpoint (1.ª invocación = cold start)")
    rt = boto3.client("sagemaker-runtime", region_name=REGION)
    fila = ",".join(["2", "0", "0", "59990", "20", "4", "35000", "34", "1"])
    for intento in (1, 2, 3):
        inicio = time.perf_counter()
        r = rt.invoke_endpoint(EndpointName=ENDPOINT, ContentType="text/csv", Accept="text/csv", Body=fila)
        ms = (time.perf_counter() - inicio) * 1000
        print(f"   invocación {intento}: probabilidad {r['Body'].read().decode().strip()} en {ms:.0f} ms")

    json.dump({"endpoint": ENDPOINT, "config": config, "modelo": modelo, "trabajo": trabajo,
               "bucket": bucket, "columnas": columnas}, open(ESTADO, "w"), indent=2)
    print(f"\nLISTO. En el .env del servidor:  ENDPOINT_MODELO={ENDPOINT}")


if __name__ == "__main__":
    main()
