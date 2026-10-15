package com.example.BackendNexusRetail.DTO;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;


public record StockItemRequest(
        @NotBlank String sku,
        @NotNull @PositiveOrZero Integer quantity
) {
}
