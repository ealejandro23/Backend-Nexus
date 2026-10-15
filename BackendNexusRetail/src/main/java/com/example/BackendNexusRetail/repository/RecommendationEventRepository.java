package com.example.BackendNexusRetail.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.example.BackendNexusRetail.model.EventType;
import com.example.BackendNexusRetail.model.ExperimentGroup;
import com.example.BackendNexusRetail.model.RecommendationEvent;

public interface RecommendationEventRepository extends JpaRepository<RecommendationEvent, Long> {

    long countByExperimentGroupAndEventType(ExperimentGroup group, EventType type);

    
    @Query("select count(distinct e.visitorId) from RecommendationEvent e "
            + "where e.experimentGroup = :expGroup and e.eventType = :evType")
    long countDistinctVisitors(@Param("expGroup") ExperimentGroup expGroup, @Param("evType") EventType evType);

    List<RecommendationEvent> findTop50ByOrderByCreatedAtDesc();
}
