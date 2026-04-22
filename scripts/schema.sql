-- Habilitar extensión para fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tabla de vehículos
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    make VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    year_start INT NOT NULL,
    year_end INT, -- 9999 representa "en adelante"
    body_type VARCHAR(100),
    roof_type VARCHAR(100) -- Ej. "Normal Roof", "Flush Rails"
);

-- Índices GIN para optimizar búsquedas difusas
CREATE INDEX IF NOT EXISTS trgm_idx_make_model ON vehicles USING gin (make gin_trgm_ops, model gin_trgm_ops);

-- Tabla de productos del catálogo Thule
CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    description TEXT
);

-- Tabla de compatibilidad (Fitments)
CREATE TABLE IF NOT EXISTS fitments (
    id SERIAL PRIMARY KEY,
    vehicle_id INT REFERENCES vehicles(id) ON DELETE CASCADE,
    weight_limit_kg DECIMAL,
    notes TEXT
);

-- Tabla de componentes para cada compatibilidad
CREATE TABLE IF NOT EXISTS fitment_components (
    fitment_id INT REFERENCES fitments(id) ON DELETE CASCADE,
    product_sku VARCHAR(50) REFERENCES products(sku) ON DELETE CASCADE,
    quantity INT DEFAULT 1,
    PRIMARY KEY (fitment_id, product_sku)
);
