# Nexo Recommender System - Documentación arc42 EP2

**Equipo:** 2  
**Curso:** ITY1102 - Arquitectura de Sistemas de Inteligencia Artificial  
**Evaluación:** Evaluación Parcial 2  
**Fecha:** 2026

---

## 1. Introducción y Objetivos

### 1.1 Descripción General de los Requisitos

Nexo Recommender es un sistema de recomendación de productos que utiliza inteligencia artificial para predecir la propensión de compra de los usuarios en diferentes categorías de productos. El sistema se integra con la tienda Shopify Plus de Nexus Retail y busca aumentar la conversión del 1,5% al 3,5% en 12 meses.

**Requisitos funcionales principales:**

| Código | Requerimiento | Prioridad |
|--------|---------------|-----------|
| RF1 | Mostrar entre 4 y 8 productos recomendados en la ficha de cada producto | Alta |
| RF2 | Personalizar la home para el usuario identificado según su historial | Alta |
| RF3 | Sugerir productos complementarios en el carrito antes del checkout | Alta |
| RF4 | Generar una lista de recomendaciones por cliente para campañas de Mailchimp | Media |
| RF5 | No recomendar productos sin stock disponible | Alta |
| RF6 | Permitir a marketing fijar un producto en un slot y vetar productos por categoría | Alta |
| RF7 | Registrar impresión, clic y compra de cada recomendación | Alta |
| RF8 | Responder algo útil para un visitante sin historial (arranque en frío) | Alta |
| RF9 | Reentrenar el modelo semanalmente y no publicarlo si empeora | Alta |
| RF10 | Un panel con conversión atribuida a recomendaciones | Media |
| RF11 | Permitir a un cliente pedir que no se use su historial (<24h) | Alta |

### 1.2 Objetivos de Calidad

| Prioridad | Atributo | Meta medible |
|-----------|----------|--------------|
| 1 | Eficiencia - Comportamiento temporal | Con 10.000 usuarios concurrentes, el 95% de las peticiones se responden en <200 ms |
| 2 | Fiabilidad - Tolerancia a fallos | Si el servicio no responde, se muestra lista de más vendidos |
| 3 | Eficiencia - Capacidad | Durante Cyber Monday, escalar 8x sin degradar latencia |

### 1.3 Interesados (Stakeholders)

| Rol | Qué espera del sistema |
|-----|-------------------------|
| Gerenta de e-commerce | Conversión 3,5% y ticket 2,0 productos |
| Jefe de tecnología | Algo que sus dos desarrolladores puedan mantener |
| Desarrolladores | Aprender y no romper el sitio |
| Encargado de cumplimiento | Perfilamiento con consentimiento y explicable |
| Cliente final | Encontrar rápido lo que busca |

---

## 2. Restricciones

### 2.1 Restricciones Técnicas

| Código | Restricción | Origen |
|--------|-------------|--------|
| RT1 | Todo corre en AWS | Contrato vigente hasta 2028 |
| RT2 | Presupuesto de USD 3.000/mes | Aprobación de directorio |
| RT3 | La tienda sigue siendo Shopify Plus | Migración cuesta más que el proyecto |
| RT4 | Admin API Shopify limitada a 2 req/seg | Límite de la plataforma |
| RT5 | No aumentar TTFB en más de 150 ms | Requerimiento de rendimiento |
| RT6 | Stock desde ERP Defontana, sincronizado cada 30 min | Contrato del ERP |
| RT7 | Modelo en Python, resto del equipo en Node | Decisión del jefe de tecnología |

### 2.2 Restricciones Organizacionales

| Código | Restricción | Origen |
|--------|-------------|--------|
| RO1 | Dos desarrolladores, 60% tiempo en mantención | Dotación actual |
| RO2 | No hay data scientist; 20 h/mes consultor | Presupuesto de personas |
| RO3 | No despliega los viernes, 1-5 de cada mes, ni Cyber | Norma interna |
| RO4 | No hay ambiente de pruebas; se prueba en producción | Deuda declarada |
| RO5 | Piloto obligatorio: 20% tráfico por 4 semanas | Exigencia de la gerenta |

### 2.3 Restricciones Normativas

| Código | Restricción | Norma |
|--------|-------------|-------|
| RN1 | Ley 19.628 y Ley 21.719 sobre protección de datos | Vigente |
| RN2 | Perfilamiento requiere consentimiento explícito y revocable | Ley 21.719 |
| RN3 | El cliente puede pedir saber por qué se le recomendó algo | Derecho a explicación |
| RN4 | Datos de clientes chilenos no salgan del país | Cumplimiento |

---

## 3. Alcance y Contexto del Sistema

### 3.1 Contexto Empresarial

El sistema Nexo se ubica entre el cliente final y la tienda Shopify Plus. Consume catálogo, stock y pedidos de Shopify, y devuelve recomendaciones que se muestran en la ficha de producto, la home y el carrito.

**Sistemas vecinos:**
- Shopify Plus (tienda y checkout)
- ERP Defontana (stock)
- Mailchimp (campañas de email)
- Google Analytics 4 (analítica)
- Zendesk (soporte)

### 3.2 Contexto Técnico

| Canal | Protocolo | Vecino |
|-------|-----------|--------|
| Lectura de catálogo | Storefront API (GraphQL) | Shopify Plus |
| Eventos de tienda | Webhooks REST/JSON | Shopify Plus |
| Sincronización de stock | CSV cada 30 min | ERP Defontana |
| Respuesta de recomendación | REST/JSON | Shopify Plus (tema) |
| Eventos de navegación | JSON por lote a S3 | Tag de clickstream |
| Recomendaciones por cliente | REST | Mailchimp |

---

## 4. Estrategia de Solución

### 4.1 Visión General

La arquitectura separa cuatro problemas que el caso mezcla en un solo encargo:

1. **Limpiar datos** que llegan sucios (sesiones duplicadas, categorías sin normalizar)
2. **Entrenar un modelo** sin romper el que ya funciona
3. **Servir una respuesta** en menos de 200 ms sin tocar Shopify en el camino crítico
4. **Permitir que marketing y cumplimiento** intervengan sin pedirle nada a tecnología

### 4.2 Decisiones Clave

| Decisión | Descripción |
|----------|-------------|
| Recomendaciones precalculadas | El modelo se entrena semanalmente y escribe listas en DynamoDB |
| Arquitectura serverless | Lambda, API Gateway, DynamoDB on-demand |
| Microservicios en contenedores | Para EP2, todo corre en Docker Compose |
| Modelo PyTorch | Red neuronal para predicción de propensión de compra |

### 4.3 Patrones Arquitectónicos

| Patrón | Justificación |
|---------|---------------|
| API Gateway | Único punto de entrada, enrutamiento, balanceo |
| Microservicios | Independencia, escalabilidad, mantenibilidad |
| Réplicas con balanceo | Alta disponibilidad, tolerancia a fallos |
| Health checks | Verificación automática de salud de servicios |

---

## 5. Vista de Bloques de Construcción

### 5.1 Nivel 1 - Contenedores

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEXO RECOMMENDER SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   FRONT     │    │  GATEWAY    │    │     IA      │    │  DOMINIO    │  │
│  │ (Streamlit) │◄──►│   (Nginx)   │◄──►│  (PyTorch)  │◄──►│  (FastAPI)  │  │
│  │             │    │             │    │             │    │             │  │
│  │ Puerto:     │    │ Puerto:     │    │ Puerto:     │    │ Puerto:     │  │
│  │ 8501        │    │ 8080        │    │ 8000        │    │ 8000        │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │                  │          │
│         │                  │                  │                  ▼          │
│         │                  │                  │           ┌─────────────┐   │
│         │                  │                  │           │     DB      │   │
│         │                  │                  │           │(PostgreSQL) │   │
│         │                  │                  │           │             │   │
│         │                  │                  │           │ Puerto:     │   │
│         │                  │                  │           │ 5432        │   │
│         │                  │                  │           └─────────────┘   │
│         │                  │                  │                              │
│         ▼                  ▼                  ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         RED INTERNA (Docker)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Nivel 2 - Componentes del Microservicio de IA

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MICROSERVICIO DE IA (Contenedor)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         API REST (FastAPI)                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │  /health    │  │  /predict   │  │/predict/batch│  │/modelo/info │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    CONTROLADOR DE PREDICCIONES                        │   │
│  │  - Validación de entrada (Pydantic)                                  │   │
│  │  - Preparación de datos para el modelo                               │   │
│  │  - Llamada al modelo PyTorch                                         │   │
│  │  - Formateo de respuesta                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      MODELO PYTORCH                                   │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  RecommenderNet                                                 │ │   │
│  │  │  - Input: 9 features                                            │ │   │
│  │  │  - Hidden: [64, 32, 16] con ReLU y Dropout                      │ │   │
│  │  │  - Output: Sigmoid (probabilidad 0-1)                           │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                    │                                  │   │
│  │                                    ▼                                  │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │  modelo_entrenado.pkl (Modelo serializado)                       │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Nivel 3 - Componentes Internos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPONENTES DEL MICROSERVICIO DE IA                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │  VALIDACIÓN     │  │  PREPROCESAMIENTO│  │  INFERENCIA     │              │
│  │  DE ENTRADA     │  │  DE DATOS        │  │  DEL MODELO     │              │
│  │                 │  │                  │  │                 │              │
│  │ - Pydantic      │  │ - Conversión a   │  │ - Carga del     │              │
│  │ - Tipos de datos│  │   DataFrame      │  │   modelo .pkl   │              │
│  │ - Rangos válidos│  │ - Orden de       │  │ - Forward pass  │              │
│  │                 │  │   columnas       │  │ - Sigmoid       │              │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Vista de Implementación

### 6.1 Diagrama de Secuencia

```
Usuario          Gateway         Front           Dominio         IA           DB
  │                │              │               │              │            │
  │  1. GET /      │              │               │              │            │
  │───────────────►│              │               │              │            │
  │                │  2. Serve    │               │              │            │
  │                │─────────────►│               │              │            │
  │                │              │               │              │            │
  │  3. POST /predict           │               │              │            │
  │─────────────────────────────────────────────────────────────────────────►│
  │                │              │               │              │            │
  │                │              │  4. POST /api/ia/predict                  │
  │                │              │──────────────────────────────►│            │
  │                │              │               │              │            │
  │                │              │               │  5. Forward pass          │
  │                │              │               │  6. Sigmoid              │
  │                │              │               │              │            │
  │                │              │  7. Response (probabilidad)  │            │
  │                │              │◄──────────────────────────────│            │
  │                │              │               │              │            │
  │                │              │  8. POST /api/dominio/prediccion         │
  │                │              │──────────────────────────────►│───────────►│
  │                │              │               │              │            │
  │                │              │               │  9. INSERT INTO predicciones
  │                │              │               │              │───────────►│
  │                │              │               │              │            │
  │                │              │  10. Response (ID)           │            │
  │                │              │◄──────────────────────────────│            │
  │                │              │               │              │            │
  │  11. Response (resultado)    │               │              │            │
  │◄─────────────────────────────────────────────────────────────────────────│
  │                │              │               │              │            │
```

### 6.2 Flujo de Fallback

Si el microservicio de IA no responde o tarda más de 200 ms:

1. El gateway detecta el timeout
2. El front muestra una lista de "más vendidos" cacheada
3. El usuario no percibe la falla

---

## 7. Vista de Implementación

### 7.1 Diagrama de Despliegue

#### Despliegue Actual (Docker Compose)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPUTADOR LOCAL                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      DOCKER NETWORK (nexo-network)                    │   │
│  │                                                                       │   │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │   │
│  │  │   GATEWAY   │    │    FRONT    │    │     IA      │               │   │
│  │  │   :8080     │    │   :8501     │    │   :8000     │               │   │
│  │  └─────────────┘    └─────────────┘    └─────────────┘               │   │
│  │         │                  │                  │                       │   │
│  │         │                  │                  │                       │   │
│  │         ▼                  ▼                  ▼                       │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    MICROSERVICIO DE DOMINIO                   │    │   │
│  │  │  ┌─────────────┐    ┌─────────────┐                         │    │   │
│  │  │  │  Réplica 1  │    │  Réplica 2  │                         │    │   │
│  │  │  │   :8000     │    │   :8000     │                         │    │   │
│  │  │  └─────────────┘    └─────────────┘                         │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │         │                                                           │   │
│  │         ▼                                                           │   │
│  │  ┌─────────────┐                                                    │   │
│  │  │     DB      │                                                    │   │
│  │  │ PostgreSQL  │                                                    │   │
│  │  │   :5432     │                                                    │   │
│  │  └─────────────┘                                                    │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Despliegue Objetivo (AWS)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AWS CLOUD (us-east-1)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         VPC (10.0.0.0/16)                            │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    AZ-1a (Zona de Disponibilidad 1)              │ │   │
│  │  │                                                                   │ │   │
│  │  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │ │   │
│  │  │  │   ALB       │    │  ECS Task   │    │  ECS Task   │          │ │   │
│  │  │  │  (Gateway)  │    │  (IA)       │    │  (Dominio)  │          │ │   │
│  │  │  │             │    │             │    │             │          │ │   │
│  │  │  │  :8080      │    │  :8000      │    │  :8000      │          │ │   │
│  │  │  └─────────────┘    └─────────────┘    └─────────────┘          │ │   │
│  │  │         │                  │                  │                  │ │   │
│  │  │         │                  │                  │                  │ │   │
│  │  │         ▼                  ▼                  ▼                  │ │   │
│  │  │  ┌─────────────────────────────────────────────────────────┐   │ │   │
│  │  │  │                    DynamoDB (Recomendaciones)             │   │ │   │
│  │  │  └─────────────────────────────────────────────────────────┘   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │   │
│  │  │                    AZ-1b (Zona de Disponibilidad 2)              │ │   │
│  │  │                                                                   │ │   │
│  │  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │ │   │
│  │  │  │  ECS Task   │    │  ECS Task   │    │  RDS         │          │ │   │
│  │  │  │  (IA)       │    │  (Dominio)  │    │  (PostgreSQL)│          │ │   │
│  │  │  │             │    │             │    │             │          │ │   │
│  │  │  │  :8000      │    │  :8000      │    │  :5432       │          │ │   │
│  │  │  └─────────────┘    └─────────────┘    └─────────────┘          │ │   │
│  │  │                                                                   │ │   │
│  │  └─────────────────────────────────────────────────────────────────┘ │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Justificación del orquestador:**

| Criterio | ECS | Kubernetes (EKS) |
|----------|-----|------------------|
| Complejidad | Baja | Alta |
| Costo | Menor | Mayor |
| Escalado | Automático | Automático |
| Curva de aprendizaje | Baja | Alta |
| **Decisión** | **✓ Elegido** | Descartado |

**Razón:** ECS es más simple de operar y tiene menor costo, adecuado para un equipo de 2 desarrolladores.

### 7.2 Recursos de Infraestructura

| Servicio | CPU | Memoria | Justificación |
|----------|-----|---------|---------------|
| Gateway | 0.25 | 128 MB | Solo enrutamiento, no requiere muchos recursos |
| Front | 0.5 | 512 MB | Streamlit es ligero |
| IA | 0.5 | 512 MB | PyTorch CPU, inferencia simple |
| Dominio (x2) | 0.5 | 512 MB | FastAPI + PostgreSQL |
| DB | 0.5 | 512 MB | PostgreSQL con datos moderados |
| Carga | 0.25 | 256 MB | Servicio one-shot |

**Total:** ~3.25 CPU, ~2.5 GB (dentro del límite de 2 GB por servicio)

### 7.3 Estimación de Costos (AWS)

| Servicio AWS | Costo mensual |
|--------------|---------------|
| AWS Lambda | $140 |
| API Gateway | $98 |
| DynamoDB | $90 |
| AWS Glue | $45 |
| AWS Fargate | $25 |
| Kinesis Firehose | $30 |
| S3 | $12 |
| Athena + QuickSight | $40 |
| CloudWatch + AppConfig | $20 |
| **Total** | **$500** |

---

## 8. Conceptos Transversales

### 8.1 Observabilidad

| Métrica | Umbral | Acción |
|---------|--------|--------|
| Latencia p95 | >200 ms | Alarma + rollback automático |
| Tasa de error | >1% | Circuit breaker + respaldo |
| CTR semanal | <-20% | Alerta a marketing |
| F1-score modelo | <0.85 | No publicar nuevo modelo |

### 8.2 Confiabilidad

| Escenario | Comportamiento | Recuperación |
|-----------|----------------|--------------|
| IA no responde | Front muestra más vendidos | Circuit breaker automático |
| Modelo nuevo peor | No se publica | Pipeline lo descarta |
| Réplica cae | Gateway redirige a otra réplica | Balanceo automático |
| BD no responde | Servicio degrada | Reintentos + alerta |

### 8.3 Seguridad y Datos Personales

| Dato | Protección | Norma |
|------|------------|-------|
| Historial compras | Cifrado en reposo | RN1, RN4 |
| Consentimiento | Estado por cliente | RN2 |
| Explicabilidad | ID de modelo registrado | RN3 |
| Datos personales | No en logs | RNF7 |

### 8.4 Modelo de Datos

El sistema utiliza PostgreSQL como base de datos relacional. A continuación se presenta el esquema de tablas:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MODELO DE DATOS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │   productos     │         │    usuarios     │                           │
│  ├─────────────────┤         ├─────────────────┤                           │
│  │ sku (PK)        │         │ usuario_id (PK) │                           │
│  │ nombre          │         │ fecha_registro  │                           │
│  │ categoria       │         │ region          │                           │
│  │ marca           │         │ comuna          │                           │
│  │ precio_lista    │         │ canal_captacion │                           │
│  │ costo           │         │ email_valido    │                           │
│  │ stock           │         │ acepta_marketing│                           │
│  │ activo          │         │ edad            │                           │
│  │ fecha_alta      │         └─────────────────┘                           │
│  └─────────────────┘                                                       │
│         │                                                                 │
│         │ 1:N                                                            │
│         ▼                                                                 │
│  ┌─────────────────┐         ┌─────────────────┐                           │
│  │  transacciones  │         │  predicciones   │                           │
│  ├─────────────────┤         ├─────────────────┤                           │
│  │ id (PK)         │         │ id (PK)         │                           │
│  │ pedido_id       │         │ usuario_id (FK) │                           │
│  │ linea           │         │ sku (FK)        │                           │
│  │ usuario_id (FK) │         │ categoria       │                           │
│  │ sku (FK)        │         │ prediccion      │                           │
│  │ fecha           │         │ propension      │                           │
│  │ cantidad        │         │ version_modelo  │                           │
│  │ precio_unitario │         │ tiempo_ms       │                           │
│  │ descuento       │         │ fecha           │                           │
│  │ total           │         └─────────────────┘                           │
│  │ canal           │                                                       │
│  │ estado          │                                                       │
│  └─────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Descripción de tablas:**

| Tabla | Descripción | Clave primaria |
|-------|-------------|----------------|
| `productos` | Catálogo de productos disponibles | `sku` |
| `usuarios` | Registro de usuarios del sistema | `usuario_id` |
| `transacciones` | Historial de compras realizadas | `id` (SERIAL) |
| `predicciones` | Registro de predicciones del modelo | `id` (SERIAL) |

**Relaciones:**
- `transacciones.usuario_id` → `usuarios.usuario_id` (N:1)
- `transacciones.sku` → `productos.sku` (N:1)
- `predicciones.usuario_id` → `usuarios.usuario_id` (N:1)
- `predicciones.sku` → `productos.sku` (N:1)

---

## 9. Decisiones de Arquitectura

### ADR-1: Recomprecalculadas vs. Tiempo Real

**Decisión:** Precalculadas

**Razón:** Latencia predecible, costo controlado, API simple de mantener.

**Costo:** Frescura limitada a la última corrida semanal.

### ADR-2: Datos en us-east-1 vs. Chile

**Decisión:** us-east-1 con cifrado y minimización

**Razón:** Viabilidad en presupuesto y plazo, acceso a catálogo completo AWS.

**Costo:** Riesgo regulatorio abierto (revisar antes de escalar).

### ADR-3: Serverless vs. Servidores Dedicados

**Decisión:** Serverless (Lambda, Fargate, DynamoDB)

**Razón:** Costo variable alineado al tráfico, sin operación de servidores.

**Costo:** Menor control fino, acoplamiento a AWS.

---

## 10. Requisitos de Calidad

### 10.1 Escenarios de Calidad

| Atributo | Estímulo | Respuesta medible |
|----------|----------|-------------------|
| Latencia | 10.000 concurrentes | 95% <200 ms |
| Tolerancia a fallos | Servicio no responde | Más vendidos, sitio no cae |
| Capacidad | Cyber Monday 8x | Sin degradación |

### 10.2 Verificación

- **Latencia:** CloudWatch p95 + prueba de carga
- **Tolerancia a fallos:** Prueba de falla controlada
- **Capacidad:** Prueba de carga + monitoreo real

---

## Anexo A: Referencias

1. Starke, G. (2023). *arc42: Template for architecture documentation*. https://arc42.org/
2. AWS (2024). *AWS Lambda Developer Guide*. AWS Documentation.
3. Aggarwal, C. C. (2016). *Recommender Systems: The Textbook*. Springer.
4. ISO (2011). *ISO/IEC 25010:2022 - Systems and software engineering*.

---

## Anexo B: Declaración de Uso de IA Generativa

| Herramienta | Uso | Verificación |
|-------------|-----|--------------|
| Claude | Redacción de documentación y código | Revisión de cifras y umbrales |
| GitHub Copilot | Sugerencias de código | Tests y revisión manual |

Los integrantes declaran que entienden el contenido de este documento y que pueden explicar y justificar cada decisión de arquitectura.

---

## Anexo C: Repositorios y Sistema

| Repositorio | URL | Tag ep2 |
|-------------|-----|---------|
| Gateway | https://github.com/nexo-recommender/gateway | ghcr.io/nexo-recommender/gateway:ep2 |
| Front | https://github.com/nexo-recommender/front | ghcr.io/nexo-recommender/front:ep2 |
| IA | https://github.com/nexo-recommender/ia | ghcr.io/nexo-recommender/ia:ep2 |
| Dominio | https://github.com/nexo-recommender/dominio | ghcr.io/nexo-recommender/dominio:ep2 |
| Carga | https://github.com/nexo-recommender/carga | ghcr.io/nexo-recommender/carga:ep2 |

**Compose.yaml:** https://github.com/nexo-recommender/main/blob/main/docker-compose.yml

**Integrantes:**

| Nombre | GitHub |
|--------|--------|
| Francisca Alarcón | @francisca-alarcon |
| Benjamín Trujillo | @benjamin-trujillo |
| Esteban Gamboa | @esteban-gamboa |
