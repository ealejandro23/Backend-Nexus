package com.example.BackendNexusRetail.DTO;

import com.example.BackendNexusRetail.model.EventType;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record EventRequest(
        @NotBlank String visitorId,
        String sourceProductId,
        @NotBlank String recommendedProductId,
        String placement,
        @NotNull EventType type
) {
}
