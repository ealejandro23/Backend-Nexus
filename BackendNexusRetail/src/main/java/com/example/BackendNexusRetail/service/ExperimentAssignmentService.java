package com.example.BackendNexusRetail.service;

import java.nio.charset.StandardCharsets;
import java.util.zip.CRC32;

import org.springframework.stereotype.Service;

import com.example.BackendNexusRetail.config.RecommendationProperties;
import com.example.BackendNexusRetail.model.ExperimentGroup;


@Service
public class ExperimentAssignmentService {

    private final RecommendationProperties props;

    public ExperimentAssignmentService(RecommendationProperties props) {
        this.props = props;
    }

    public ExperimentGroup assign(String visitorId) {
        return bucket(visitorId) < props.pilotPercentage() ? ExperimentGroup.PILOT : ExperimentGroup.CONTROL;
    }

    /** Número entre 0 y 99 derivado del visitorId y la sal del experimento. */
    int bucket(String visitorId) {
        CRC32 crc = new CRC32();
        crc.update((props.experimentSalt() + ":" + visitorId).getBytes(StandardCharsets.UTF_8));
        return (int) (crc.getValue() % 100);
    }
}
