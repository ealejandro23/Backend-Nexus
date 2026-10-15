package com.example.BackendNexusRetail.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**

 
  @param resultSize       
  @param candidatePool    
  @param stockBuffer      
                          
  @param pilotPercentage
  @param experimentSalt
 */
@ConfigurationProperties(prefix = "app.recommendation")
public record RecommendationProperties(
        int resultSize,
        int candidatePool,
        int stockBuffer,
        int pilotPercentage,
        String experimentSalt
) {
    public RecommendationProperties {
        if (resultSize <= 0) resultSize = 8;
        if (candidatePool <= 0) candidatePool = 50;
        if (stockBuffer < 0) stockBuffer = 3;
        if (pilotPercentage < 0 || pilotPercentage > 100) pilotPercentage = 20;
        if (experimentSalt == null || experimentSalt.isBlank()) experimentSalt = "nexus-pilot-1";
    }
}
