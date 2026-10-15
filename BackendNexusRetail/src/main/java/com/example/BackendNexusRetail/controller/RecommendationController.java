package com.example.BackendNexusRetail.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.BackendNexusRetail.DTO.RecommendationResponse;
import com.example.BackendNexusRetail.service.RecommendationService;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

@RestController
@RequestMapping("/api/recommendations")
public class RecommendationController {

    private final RecommendationService service;

    public RecommendationController(RecommendationService service) {
        this.service = service;
    }

    /** Ejemplo: GET /api/recommendations?visitorId=abc123&productId=SKU-1001&limit=8 */
    @GetMapping
    public RecommendationResponse recommend(
            @RequestParam @NotBlank String visitorId,
            @RequestParam @NotBlank String productId,
            @RequestParam(required = false) @Min(1) @Max(24) Integer limit) {
        return service.recommend(visitorId, productId, limit);
    }
}