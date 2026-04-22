import pandas as pd
import numpy as np
import os
import re
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración DB
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def parse_year_range(year_str):
    """Convierte '2018-', '2010-2015', 'A' en start/end"""
    if pd.isna(year_str) or str(year_str).strip() == "":
        return None, None
    
    year_str = str(year_str).strip().upper()
    
    # Caso "A" (Active/Actual) -> Asumimos año actual o futuro lejano
    if year_str == "A":
        return 2024, None 
        
    # Buscar patrón numérico
    match = re.match(r"(\d{4})-?(\d{4})?", year_str)
    if match:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else None
        return start, end
        
    return None, None

def process_recommendation_list(file_path):
    """Procesa 'Recommendation List RMS 2025-09.xlsx'"""
    print(f"📂 Procesando: {os.path.basename(file_path)}")
    df = pd.read_excel(file_path)
    
    # Normalizar nombres de columnas (eliminar espacios y saltos de línea)
    df.columns = [col.strip().replace('\n', ' ').lower() for col in df.columns]
    
    # Mapeo de columnas según tu Excel
    # Nota: Ajusta estos nombres si difieren ligeramente en tu archivo real
    brand_col = 'car make' if 'car make' in df.columns else 'car maker'
    model_col = 'car model'
    type_col = 'car type'
    year_col = 'start year'
    
    if brand_col not in df.columns:
        print(f"⚠️ Columna '{brand_col}' no encontrada. Revisa el Excel.")
        return pd.DataFrame()

    df['brand'] = df[brand_col].str.upper().str.strip()
    df['model'] = df[model_col].str.title().str.strip()
    df['type'] = df[type_col].str.strip() if type_col in df.columns else 'Unknown'
    
    # Extraer años
    years = df[year_col].apply(parse_year_range)
    df['year_start'] = [y[0] for y in years]
    df['year_end'] = [y[1] for y in years]
    
    # Filtrar filas sin año válido
    df = df.dropna(subset=['year_start'])
    
    # Extraer productos compatibles (Columnas como 'Hanging 2B - 994001')
    # Buscamos columnas que contengan SKU de Thule (6 dígitos) o nombres conocidos
    product_cols = [col for col in df.columns if any(x in col.lower() for x in ['hanging', 'platform', 'outway', '993001', '994001', '995001'])]
    
    vehicles_data = []
    fitments_data = []
    products_seen = set()

    for _, row in df.iterrows():
        # Crear registro de vehículo
        v_id_key = (row['brand'], row['model'], row['year_start'], row['year_end'], row['type'])
        
        # Aquí simplificamos: Insertamos vehículos y luego buscamos su ID
        # En producción real, haríamos un UPSERT y recuperaríamos el ID
        
        for p_col in product_cols:
            val = str(row[p_col]).strip().upper()
            # Si hay una 'X' o un valor que no sea 'NO' o vacío, asumimos compatible
            is_compat = val == 'X' or (val != 'NO' and val != '' and val != 'N/A')
            
            # Extraer SKU de la columna (ej: "Hanging 2B - 994001" -> "994001")
            sku_match = re.search(r'\d{6}', p_col)
            if not sku_match: continue
            sku = sku_match.group(0)
            
            # Nombre del producto basado en la columna
            prod_name = p_col.split('-')[0].strip() if '-' in p_col else p_col
            
            if sku not in products_seen:
                products_seen.add(sku)
                # Insertar producto básico
                print(f"   📦 Producto detectado: {sku} - {prod_name}")

            # Guardar datos para inserción masiva después
            fitments_data.append({
                'brand': row['brand'],
                'model': row['model'],
                'year_start': row['year_start'],
                'year_end': row['year_end'],
                'type': row['type'],
                'product_sku': sku,
                'is_compatible': is_compat,
                'fitment_notes': '', # Podrías extraer comentarios si existen
                'pad_type': '',
                'reinforcement_strap': False,
                'engineering_comment': ''
            })

    return pd.DataFrame(fitments_data)

def main():
    engine = create_engine(DATABASE_URL)
    raw_folder = 'data/raw'
    
    all_fitments = []
    
    # 1. Procesar Recommendation List
    rec_file = os.path.join(raw_folder, "Recommendation List RMS 2025-09.xlsx")
    if os.path.exists(rec_file):
        fit_df = process_recommendation_list(rec_file)
        all_fitments.append(fit_df)

    if not all_fitments:
        print("❌ No se encontraron datos válidos.")
        return

    final_df = pd.concat(all_fitments, ignore_index=True)
    print(f"✅ Total de registros de compatibilidad: {len(final_df)}")

    # Inserción en BD (Paso a paso para manejar relaciones)
    with engine.connect() as conn:
        for index, row in final_df.iterrows():
            # 1. Insertar o obtener Vehicle ID
            result = conn.execute(text("""
                INSERT INTO vehicles (brand, model, type, year_start, year_end)
                VALUES (:brand, :model, :type, :year_start, :year_end)
                ON CONFLICT (brand, model, year_start, COALESCE(year_end, 9999), COALESCE(type, '')) 
                DO UPDATE SET brand=EXCLUDED.brand
                RETURNING id;
            """), {
                'brand': row['brand'],
                'model': row['model'],
                'type': row['type'],
                'year_start': row['year_start'],
                'year_end': row['year_end']
            })
            v_id = result.scalar()

            # 2. Insertar Producto si no existe
            conn.execute(text("""
                INSERT INTO products (sku, name, category)
                VALUES (:sku, :name, 'Bike Rack')
                ON CONFLICT (sku) DO NOTHING;
            """), {
                'sku': row['product_sku'],
                'name': f"Thule Product {row['product_sku']}" # Mejorar nombre con lookup externo
            })

            # 3. Insertar Fitment
            conn.execute(text("""
                INSERT INTO vehicle_product_fitment (vehicle_id, product_sku, is_compatible, fitment_notes)
                VALUES (:v_id, :sku, :is_compat, :notes)
                ON CONFLICT (vehicle_id, product_sku) DO UPDATE SET
                    is_compatible = EXCLUDED.is_compatible;
            """), {
                'v_id': v_id,
                'sku': row['product_sku'],
                'is_compat': row['is_compatible'],
                'notes': row['fitment_notes']
            })
            
            if index % 100 == 0:
                conn.commit()
                print(f"   ... procesados {index} registros")
        
        conn.commit()
        print("💾 Datos insertados correctamente en PostgreSQL.")

if __name__ == "__main__":
    main()
