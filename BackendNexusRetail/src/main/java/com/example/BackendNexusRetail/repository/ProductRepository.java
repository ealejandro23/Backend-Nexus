package com.example.BackendNexusRetail.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.BackendNexusRetail.model.Product;

public interface ProductRepository extends JpaRepository<Product, Long> {

    Optional<Product> findBySku(String sku);
}
