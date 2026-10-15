package com.example.BackendNexusRetail.config;

import java.util.List;
import java.util.Random;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import com.example.BackendNexusRetail.service.RedisKeys;


@Component
@Profile("dev")
public class DevDataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DevDataSeeder.class);

    private final StringRedisTemplate redis;

    public DevDataSeeder(StringRedisTemplate redis) {
        this.redis = redis;
    }

    @Override
    public void run(String... args) {
        Random random = new Random(42);
        int total = 30;
        List<String> skus = new java.util.ArrayList<>();

        for (int i = 1; i <= total; i++) {
            String sku = "SKU-" + (1000 + i);
            skus.add(sku);
            // algunos productos quedan sin stock o con stock bajo a propósito
            int stock = (i % 5 == 0) ? 0 : (i % 7 == 0) ? 2 : 5 + random.nextInt(50);
            redis.opsForValue().set(RedisKeys.stock(sku), String.valueOf(stock));
            redis.opsForZSet().add(RedisKeys.POPULAR, sku, 1000 - i);
        }

        // candidatos "item-item" para los primeros 5 productos
        for (int p = 0; p < 5; p++) {
            String source = skus.get(p);
            for (int c = 0; c < total; c++) {
                String candidate = skus.get(c);
                if (!candidate.equals(source)) {
                    redis.opsForZSet().add(RedisKeys.similar(source), candidate, random.nextDouble());
                }
            }
        }
        log.info("Datos de prueba cargados en Redis: {} SKUs (prueba con productId=SKU-1001)", total);
    }
}
