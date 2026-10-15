package com.example.BackendNexusRetail.model;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Evento de medición del piloto: impresión, clic, carrito o compra de un producto recomendado. */
@Entity
@Table(name = "recommendation_events", indexes = {
        @Index(name = "idx_events_group_type", columnList = "experiment_group, event_type"),
        @Index(name = "idx_events_created_at", columnList = "created_at")
})
@Getter
@Setter
@NoArgsConstructor
public class RecommendationEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "visitor_id", nullable = false, length = 128)
    private String visitorId;

    @Column(name = "source_product_id", length = 64)
    private String sourceProductId;

    @Column(name = "recommended_product_id", nullable = false, length = 64)
    private String recommendedProductId;

    @Column(length = 64)
    private String placement;

    @Enumerated(EnumType.STRING)
    @Column(name = "event_type", nullable = false, length = 32)
    private EventType eventType;

    @Enumerated(EnumType.STRING)
    @Column(name = "experiment_group", nullable = false, length = 16)
    private ExperimentGroup experimentGroup;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt = Instant.now();
}
