package com.example.BackendNexusRetail.assemblers;

import java.util.List;

import org.springframework.stereotype.Component;

import com.example.BackendNexusRetail.DTO.RecommendationItem;
import com.example.BackendNexusRetail.DTO.RecommendationResponse;
import com.example.BackendNexusRetail.model.ExperimentGroup;


@Component
public class RecommendationAssembler {

    public RecommendationResponse toResponse(String visitorId, String sourceProductId, ExperimentGroup group,
                                             List<RecommendationItem> items, boolean fallbackUsed, int discarded) {
        return new RecommendationResponse(visitorId, sourceProductId, group, items, fallbackUsed, discarded);
    }

    
    public RecommendationResponse controlResponse(String visitorId, String sourceProductId) {
        return new RecommendationResponse(visitorId, sourceProductId, ExperimentGroup.CONTROL, List.of(), false, 0);
    }
}
