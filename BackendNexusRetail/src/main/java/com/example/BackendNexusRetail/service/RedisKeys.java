package com.example.BackendNexusRetail.service;

/** Claves de Redis usadas por el sistema, centralizadas para no repetir strings. */
public final class RedisKeys {

    /** ZSET global de productos más vendidos (fallback). */
    public static final String POPULAR = "reco:popular";

    private RedisKeys() {
    }

    /** STRING con la cantidad disponible de un SKU. */
    public static String stock(String sku) {
        return "stock:" + sku;
    }

    /** ZSET de productos similares a uno dado (score = similitud). Lo llena el job batch. */
    public static String similar(String productId) {
        return "reco:similar:" + productId;
    }
}

