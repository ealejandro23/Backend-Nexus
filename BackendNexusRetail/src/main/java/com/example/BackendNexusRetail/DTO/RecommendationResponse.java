package com.example.BackendNexusRetail.DTO;

import java.util.List;

import com.example.BackendNexusRetail.model.ExperimentGroup;

/**
 * Respuesta de GET /api/recommendations.
 *
 * @param group        PILOT o CONTROL. En CONTROL la lista viene vacía: Shopify muestra su bloque habitual.
 * @param fallbackUsed true si hubo que completar con "más vendidos" porque los candidatos con stock no alcanzaron.
 * @param discardedOutOfStock cuántos candidatos se descartaron por stock (métrica clave para el directorio).
 */
public record RecommendationResponse(
        String visitorId,
        String sourceProductId,
        ExperimentGroup group,
        List<RecommendationItem> items,
        boolean fallbackUsed,
        int discardedOutOfStock
) {
}
