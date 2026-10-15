package com.example.BackendNexusRetail.controller;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.example.BackendNexusRetail.DTO.StockItemRequest;
import com.example.BackendNexusRetail.DTO.StockUpdateRequest;
import com.example.BackendNexusRetail.service.StockSnapshotService;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;

/**
 * Endpoints para mantener el snapshot de stock:
 *  - PUT / POST bulk: los usa el job que sincroniza con el ERP (cada pocos minutos).
 *  - POST decrement: lo usa el webhook de pedidos de Shopify para descontar al instante.
 *
 * TODO antes de producción: proteger con API key o Spring Security y validar la firma HMAC de Shopify.
 */
@RestController
@RequestMapping("/api/stock")
public class StockController {

    private final StockSnapshotService service;

    public StockController(StockSnapshotService service) {
        this.service = service;
    }

    @GetMapping("/{sku}")
    public Map<String, Object> get(@PathVariable String sku) {
        Map<String, Object> body = new LinkedHashMap<>();
        Integer quantity = service.getStock(sku);
        body.put("sku", sku);
        body.put("quantity", quantity);
        body.put("available", quantity != null && service.isAvailable(quantity));
        return body;
    }

    @PutMapping("/{sku}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void update(@PathVariable String sku, @Valid @RequestBody StockUpdateRequest request) {
        service.setStock(sku, request.quantity());
    }

    @PostMapping("/bulk")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void bulk(@RequestBody List<@Valid StockItemRequest> items) {
        Map<String, Integer> map = new LinkedHashMap<>();
        items.forEach(item -> map.put(item.sku(), item.quantity()));
        service.setStockBulk(map);
    }

    @PostMapping("/{sku}/decrement")
    public Map<String, Object> decrement(@PathVariable String sku,
                                         @RequestParam(defaultValue = "1") @Min(1) int units) {
        long remaining = service.decrement(sku, units);
        return Map.of("sku", sku, "quantity", remaining);
    }
}

