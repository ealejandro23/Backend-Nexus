package com.example.BackendNexusRetail.controller;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.example.BackendNexusRetail.DTO.EventRequest;
import com.example.BackendNexusRetail.DTO.ExperimentReport;
import com.example.BackendNexusRetail.service.EventTrackingService;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api")
public class EventController {

    private final EventTrackingService service;

    public EventController(EventTrackingService service) {
        this.service = service;
    }

    /** Impresión, clic, carrito o compra de un producto recomendado. */
    @PostMapping("/events")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public void record(@Valid @RequestBody EventRequest request) {
        service.record(request);
    }

    /** Resultado del piloto: conversión del grupo PILOT vs. CONTROL. */
    @GetMapping("/experiment/report")
    public ExperimentReport report() {
        return service.report();
    }
}
