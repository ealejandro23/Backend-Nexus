package com.example.BackendNexusRetail.DTO;


public record ExperimentReport(
        long pilotImpressionVisitors,
        long pilotPurchaseVisitors,
        long controlImpressionVisitors,
        long controlPurchaseVisitors,
        double pilotConversionPct,
        double controlConversionPct
) {
}
