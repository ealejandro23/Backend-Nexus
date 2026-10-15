package com.example.BackendNexusRetail.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;


@Configuration
@EnableConfigurationProperties(RecommendationProperties.class)
public class AppConfig {
}