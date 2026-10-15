package com.example.BackendNexusRetail.service;

import org.springframework.stereotype.Service;

import com.example.BackendNexusRetail.DTO.EventRequest;
import com.example.BackendNexusRetail.DTO.ExperimentReport;
import com.example.BackendNexusRetail.model.EventType;
import com.example.BackendNexusRetail.model.ExperimentGroup;
import com.example.BackendNexusRetail.model.RecommendationEvent;
import com.example.BackendNexusRetail.repository.RecommendationEventRepository;


@Service
public class EventTrackingService {

    private final RecommendationEventRepository repository;
    private final ExperimentAssignmentService experimentService;

    public EventTrackingService(RecommendationEventRepository repository,
                                ExperimentAssignmentService experimentService) {
        this.repository = repository;
        this.experimentService = experimentService;
    }

    public void record(EventRequest request) {
        RecommendationEvent event = new RecommendationEvent();
        event.setVisitorId(request.visitorId());
        event.setSourceProductId(request.sourceProductId());
        event.setRecommendedProductId(request.recommendedProductId());
        event.setPlacement(request.placement());
        event.setEventType(request.type());
        event.setExperimentGroup(experimentService.assign(request.visitorId()));
        repository.save(event);
    }

    
    public ExperimentReport report() {
        long pilotSeen = repository.countDistinctVisitors(ExperimentGroup.PILOT, EventType.IMPRESSION);
        long pilotBought = repository.countDistinctVisitors(ExperimentGroup.PILOT, EventType.PURCHASE);
        long controlSeen = repository.countDistinctVisitors(ExperimentGroup.CONTROL, EventType.IMPRESSION);
        long controlBought = repository.countDistinctVisitors(ExperimentGroup.CONTROL, EventType.PURCHASE);
        return new ExperimentReport(
                pilotSeen, pilotBought, controlSeen, controlBought,
                pct(pilotBought, pilotSeen), pct(controlBought, controlSeen));
    }

    private static double pct(long part, long total) {
        return total == 0 ? 0.0 : Math.round(part * 10000.0 / total) / 100.0;
    }
}
