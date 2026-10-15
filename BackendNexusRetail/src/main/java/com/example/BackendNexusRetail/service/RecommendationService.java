package com.example.BackendNexusRetail.service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ZSetOperations.TypedTuple;
import org.springframework.stereotype.Service;

import com.example.BackendNexusRetail.DTO.RecommendationItem;
import com.example.BackendNexusRetail.DTO.RecommendationResponse;
import com.example.BackendNexusRetail.assemblers.RecommendationAssembler;
import com.example.BackendNexusRetail.config.RecommendationProperties;
import com.example.BackendNexusRetail.model.ExperimentGroup;


@Service
public class RecommendationService {

    private static final Logger log = LoggerFactory.getLogger(RecommendationService.class);

    private final StringRedisTemplate redis;
    private final StockSnapshotService stockService;
    private final ExperimentAssignmentService experimentService;
    private final RecommendationAssembler assembler;
    private final RecommendationProperties props;

    public RecommendationService(StringRedisTemplate redis,
                                 StockSnapshotService stockService,
                                 ExperimentAssignmentService experimentService,
                                 RecommendationAssembler assembler,
                                 RecommendationProperties props) {
        this.redis = redis;
        this.stockService = stockService;
        this.experimentService = experimentService;
        this.assembler = assembler;
        this.props = props;
    }

    public RecommendationResponse recommend(String visitorId, String productId, Integer requestedLimit) {
        ExperimentGroup group = experimentService.assign(visitorId);
        if (group == ExperimentGroup.CONTROL) {
            return assembler.controlResponse(visitorId, productId);
        }

        int limit = requestedLimit != null ? requestedLimit : props.resultSize();

        // 1) candidatos item-item del producto
        Map<String, Double> similar = readCandidates(RedisKeys.similar(productId), productId);
        Set<String> availableSimilar = stockService.filterAvailable(similar.keySet());

        Map<String, Double> chosen = new LinkedHashMap<>();
        int discarded = 0;
        for (Map.Entry<String, Double> candidate : similar.entrySet()) {
            if (availableSimilar.contains(candidate.getKey())) {
                if (chosen.size() < limit) {
                    chosen.put(candidate.getKey(), candidate.getValue());
                }
            } else {
                discarded++;
            }
        }

        // 2) fallback: más vendidos con stock
        boolean fallbackUsed = false;
        if (chosen.size() < limit) {
            fallbackUsed = true;
            Map<String, Double> popular = readCandidates(RedisKeys.POPULAR, productId);
            popular.keySet().removeAll(chosen.keySet());
            Set<String> availablePopular = stockService.filterAvailable(popular.keySet());
            for (Map.Entry<String, Double> candidate : popular.entrySet()) {
                if (chosen.size() >= limit) {
                    break;
                }
                if (availablePopular.contains(candidate.getKey())) {
                    chosen.put(candidate.getKey(), candidate.getValue());
                }
            }
        }

        List<RecommendationItem> items = new ArrayList<>();
        chosen.forEach((id, score) -> items.add(new RecommendationItem(id, score)));

        if (discarded > 0) {
            log.debug("productId={} candidatos descartados por stock: {}", productId, discarded);
        }
        return assembler.toResponse(visitorId, productId, group, items, fallbackUsed, discarded);
    }

    /** Lee un ZSET de Redis (mayor score primero), excluyendo el propio producto. */
    private Map<String, Double> readCandidates(String key, String excludeProductId) {
        Set<TypedTuple<String>> tuples = redis.opsForZSet()
                .reverseRangeWithScores(key, 0, props.candidatePool() - 1L);
        Map<String, Double> result = new LinkedHashMap<>();
        if (tuples == null) {
            return result;
        }
        for (TypedTuple<String> tuple : tuples) {
            String id = tuple.getValue();
            if (id != null && !id.equals(excludeProductId)) {
                result.put(id, tuple.getScore() == null ? 0.0 : tuple.getScore());
            }
        }
        return result;
    }
}
