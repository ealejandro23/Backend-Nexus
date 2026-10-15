package com.example.BackendNexusRetail.service;

import java.util.Collection;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import com.example.BackendNexusRetail.config.RecommendationProperties;


@Service
public class StockSnapshotService {

    private final StringRedisTemplate redis;
    private final RecommendationProperties props;

    public StockSnapshotService(StringRedisTemplate redis, RecommendationProperties props) {
        this.redis = redis;
        this.props = props;
    }

    public void setStock(String sku, int quantity) {
        redis.opsForValue().set(RedisKeys.stock(sku), String.valueOf(quantity));
    }

    public void setStockBulk(Map<String, Integer> stockBySku) {
        stockBySku.forEach(this::setStock);
    }

    /** Descuenta unidades (por ejemplo cuando llega un pedido nuevo desde Shopify). */
    public long decrement(String sku, int units) {
        Long result = redis.opsForValue().decrement(RedisKeys.stock(sku), units);
        return result == null ? 0 : result;
    }

    public Integer getStock(String sku) {
        String value = redis.opsForValue().get(RedisKeys.stock(sku));
        return value == null ? null : Integer.valueOf(value);
    }

    /**
     * De una lista de SKUs, devuelve los que se consideran disponibles.
     * Una sola llamada a Redis (MGET) para toda la lista: clave para mantenerse bajo 200 ms.
     */
    public Set<String> filterAvailable(Collection<String> skus) {
        if (skus.isEmpty()) {
            return Set.of();
        }
        List<String> ordered = List.copyOf(skus);
        List<String> keys = ordered.stream().map(RedisKeys::stock).toList();
        List<String> values = redis.opsForValue().multiGet(keys);

        Set<String> available = new HashSet<>();
        if (values == null) {
            return available;
        }
        for (int i = 0; i < ordered.size(); i++) {
            String raw = values.get(i);
            if (raw != null && isAvailable(Integer.parseInt(raw))) {
                available.add(ordered.get(i));
            }
        }
        return available;
    }

    /** Regla de disponibilidad con colchón de seguridad. */
    public boolean isAvailable(int quantity) {
        return quantity > props.stockBuffer();
    }

    /** Útil para depurar: stock actual de varios SKUs. */
    public Map<String, Integer> snapshot(Collection<String> skus) {
        Map<String, Integer> result = new LinkedHashMap<>();
        for (String sku : skus) {
            result.put(sku, getStock(sku));
        }
        return result;
    }
}

