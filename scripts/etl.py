import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
DEFAULT_RAW_DATA_DIR = Path(__file__).resolve().parent.parent / 'data' / 'raw'
DEFAULT_EXCEL_FILES = (
    'Fit Guide Thule Professional 2025-03-05.xlsx',
    'New Rec Roof Racks_Rapid and Next gen_2025-10-01.xlsx',
    'Recommendation List RMS 2025-09.xlsx',
)
REQUIRED_DB_ENV = ('DB_USER', 'DB_PASS', 'DB_HOST', 'DB_PORT', 'DB_NAME')
MIN_COMPATIBILITY_PRECISION_PERCENT = 90.0


def emit_structured_event(
    event: str,
    *,
    stage: str,
    payload: Dict[str, Any],
    conversation_id: Optional[str] = None,
    snapshot_version: Optional[str] = None,
    error_code: Optional[str] = None,
) -> None:
    envelope = {
        'event': event,
        'stage': stage,
        'conversation_id': conversation_id,
        'snapshot_version': snapshot_version,
        'error_code': error_code,
    }
    envelope.update(payload)
    print(json.dumps(envelope, ensure_ascii=True))


def build_database_uri() -> str:
    missing = [name for name in REQUIRED_DB_ENV if not os.getenv(name)]
    if missing:
        raise EnvironmentError(
            'Faltan variables de entorno de BD: '
            + ', '.join(missing)
            + '. Defina estas variables antes de ejecutar ETL.'
        )
    return (
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='ETL de fitment Thule (Excel -> PostgreSQL).'
    )
    parser.add_argument(
        '--run-migrations',
        action='store_true',
        help='Ejecuta scripts SQL de migracion antes de cargar datos (por defecto: desactivado).',
    )
    parser.add_argument(
        '--migrations-dir',
        default=str(DEFAULT_MIGRATIONS_DIR),
        help='Directorio de migraciones SQL ejecutadas en orden lexicografico.',
    )
    parser.add_argument(
        '--raw-data-dir',
        default=str(DEFAULT_RAW_DATA_DIR),
        help='Directorio base para archivos Excel cuando no se usa --excel-file.',
    )
    parser.add_argument(
        '--excel-file',
        action='append',
        default=[],
        help='Ruta de archivo Excel a procesar (se puede repetir).',
    )
    parser.add_argument(
        '--allow-quality-warnings',
        action='store_true',
        help='Permite continuar aun con issues de calidad no criticos.',
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def run_sql_migrations(engine, migrations_dir: str) -> None:
    migrations_path = Path(migrations_dir).expanduser().resolve()
    if not migrations_path.exists():
        raise FileNotFoundError(f'Directorio de migraciones no encontrado: {migrations_path}')

    migration_files = sorted(migrations_path.glob('*.sql'))
    if not migration_files:
        print(f'No se encontraron migraciones SQL en {migrations_path}')
        return

    print(f'Ejecutando {len(migration_files)} migraciones desde {migrations_path}...')
    raw_conn = engine.raw_connection()
    try:
        raw_conn.autocommit = True
        with raw_conn.cursor() as cursor:
            for migration_file in migration_files:
                script = migration_file.read_text(encoding='utf-8').strip()
                if not script:
                    print(f'Saltando migracion vacia: {migration_file.name}')
                    continue
                print(f' - Aplicando {migration_file.name}')
                cursor.execute(script)
    finally:
        raw_conn.close()


def get_latest_tecbite_commerce_by_sku(engine, sku: str) -> Optional[Dict[str, Any]]:
    if not sku:
        return None

    query = text(
        """
        WITH latest_snapshot AS (
            SELECT snapshot_id, snapshot_at
            FROM tecbite_catalog_snapshot
            WHERE status IN ('success', 'partial')
            ORDER BY snapshot_at DESC
            LIMIT 1
        )
        SELECT
            ps.product_sku,
            ps.title,
            ps.price_amount,
            ps.currency,
            ps.stock_status,
            ps.promo_text,
            ps.source_url,
            ps.fresh_until,
            ls.snapshot_at
        FROM latest_snapshot ls
        JOIN tecbite_product_state ps ON ps.snapshot_id = ls.snapshot_id
        WHERE ps.product_sku = :sku
        ORDER BY ps.ingested_at DESC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {'sku': sku}).mappings().first()
    return dict(row) if row else None


def get_thule_chunks_for_query(
    engine,
    query_text: str,
    limit: int = 5,
    source: str = 'thule.com',
    locale: str = 'es-PA',
) -> List[Dict[str, Any]]:
    clean_query = (query_text or '').strip()
    like_query = f'%{clean_query}%'

    primary_query = text(
        """
        SELECT
            c.chunk_id,
            c.chunk_text,
            d.source_url,
            d.locale,
            COALESCE(c.metadata->>'source', '') AS source
        FROM thule_document_chunk c
        JOIN thule_document d ON d.doc_id = c.doc_id
        WHERE d.is_active = TRUE
          AND d.locale = :locale
          AND LOWER(COALESCE(c.metadata->>'source', '')) = LOWER(:source)
          AND c.chunk_text ILIKE :like_query
        ORDER BY c.created_at DESC
        LIMIT :limit
        """
    )

    fallback_query = text(
        """
        SELECT
            c.chunk_id,
            c.chunk_text,
            d.source_url,
            d.locale,
            COALESCE(c.metadata->>'source', '') AS source
        FROM thule_document_chunk c
        JOIN thule_document d ON d.doc_id = c.doc_id
        WHERE d.is_active = TRUE
          AND d.locale = :locale
          AND LOWER(COALESCE(c.metadata->>'source', '')) = LOWER(:source)
        ORDER BY c.created_at DESC
        LIMIT :limit
        """
    )

    params = {'locale': locale, 'source': source, 'like_query': like_query, 'limit': int(limit)}
    with engine.connect() as conn:
        if clean_query:
            rows = conn.execute(primary_query, params).mappings().all()
            if rows:
                return [dict(row) for row in rows]
        rows = conn.execute(fallback_query, params).mappings().all()
        return [dict(row) for row in rows]

def normalize_column_name(name):
    name = str(name).replace('\n', ' ')
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name

def clean_string(val):
    if pd.isna(val):
        return None
    val = str(val).strip()
    if val.lower() in ['no fit', 'n/a', 'none', 'null', '']:
        return None
    return val.title()

def parse_years(year_str):
    if pd.isna(year_str):
        return None, None
    year_str = str(year_str).strip()
    match_open = re.match(r'^(\d{2,4})-$', year_str)
    if match_open:
        start = int(match_open.group(1))
        start = start + 2000 if start < 100 else start
        return start, 9999
    match_range = re.match(r'^(\d{2,4})-(\d{2,4})$', year_str)
    if match_range:
        start = int(match_range.group(1))
        end = int(match_range.group(2))
        start = start + 2000 if start < 100 else start
        end = end + 2000 if end < 100 else end
        return start, end
    match_single = re.match(r'^(\d{2,4})$', year_str)
    if match_single:
        year = int(match_single.group(1))
        year = year + 2000 if year < 100 else year
        return year, year
    return None, None

def normalize_sku_token(token):
    token = str(token).strip().upper()
    token = re.sub(r'\.0+$', '', token)
    if token in ['', 'NAN', 'NONE', 'NULL', 'N/A', 'NO', 'NO FIT']:
        return None
    return token

def parse_sku_list(value):
    if pd.isna(value):
        return []
    value = str(value).strip()
    if not value:
        return []

    tokens = []
    for part in re.split(r'[,;/]+', value):
        normalized = normalize_sku_token(part)
        if normalized:
            tokens.append(normalized)
    return list(dict.fromkeys(tokens))

def normalize_sku_cell(value):
    skus = parse_sku_list(value)
    if not skus:
        return None
    return ', '.join(skus)

def extract_single_sku(value, max_len=20):
    skus = parse_sku_list(value)
    for sku in skus:
        if len(sku) <= max_len:
            return sku
    return None

def is_compatible_marker(value):
    if pd.isna(value):
        return False
    marker = str(value).strip().lower()
    return marker in {'x', 'yes', 'true', '1', 'si', 'sí', 'y'}

def parse_yes_no_bool(value):
    if pd.isna(value):
        return None
    marker = str(value).strip().lower()
    if marker in {'yes', 'true', '1', 'si', 'sí', 'y'}:
        return True
    if marker in {'no', 'false', '0', 'n'}:
        return False
    return None

def coalesce_columns(frame, candidates):
    existing = [c for c in candidates if c in frame.columns]
    if not existing:
        return pd.Series([None] * len(frame), index=frame.index)
    return frame[existing].replace('', pd.NA).bfill(axis=1).iloc[:, 0]

def process_excel_files(file_paths):
    all_data = []
    
    column_mapping = {
        'brand': 'brand',
        'make': 'brand',
        'car make': 'brand',
        'car maker': 'brand',
        'model': 'model',
        'car model': 'model',
        'car model ': 'model',
        'car model': 'model',
        'car model': 'model',
        'car type': 'type',
        'car type ': 'type',
        'body type': 'type',
        'roof type': 'roof_type',
        'year': 'year_str',
        'years': 'year_str',
        'car year': 'year_str',
        'start year': 'year_start_raw',
        'stop year': 'year_end_raw',
        'end year': 'year_end_raw',
        'no of doors': 'doors',
        'generation': 'generation',
        'kit': 'kit_sku',
        'bar': 'bar_front_sku',
        'foot': 'foot_pack_sku',
        'notes': 'fitment_notes',
        'engineering comment': 'engineering_comment'
    }

    for file_path in file_paths:
        if not os.path.exists(file_path):
            print(f"Advertencia: Archivo no encontrado {file_path}")
            continue
        print(f"Procesando {file_path}...")
        try:
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                if df.empty:
                    continue

                df.columns = [normalize_column_name(c) for c in df.columns]
                df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

                if df.columns.duplicated().any():
                    df = df.groupby(df.columns, axis=1).first()

                df['source_file'] = os.path.basename(file_path)
                df['source_sheet'] = sheet_name
                all_data.append(df)
        except Exception as e:
            print(f"Error al leer {file_path}: {e}")
            
    if not all_data:
        return pd.DataFrame()
        
    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df

def transform_data(df):
    if df.empty:
        return df
    
    print(f"Columnas combinadas: {df.columns.tolist()}")
    
    for col in ['brand', 'model', 'type', 'roof_type', 'generation']:
        if col in df.columns:
            df[col] = df[col].apply(clean_string)
            
    if 'brand' in df.columns and 'model' in df.columns:
        # Solo mantener filas que tengan marca y modelo
        df = df.dropna(subset=['brand', 'model']).copy()
    else:
        print("ADVERTENCIA: No se encontró la columna 'brand' o 'model' en los datos.")
        return pd.DataFrame()
        
    # Procesar años
    if 'year_start' not in df.columns:
        df['year_start'] = None
    if 'year_end' not in df.columns:
        df['year_end'] = None

    if 'year_str' in df.columns:
        years = df['year_str'].apply(parse_years)
        df['year_start'] = [y[0] if pd.notna(y[0]) else None for y in years]
        df['year_end'] = [y[1] if pd.notna(y[1]) else None for y in years]
        
    if 'year_start_raw' in df.columns:
        # Rellenar los nulos de year_start con year_start_raw
        df['year_start'] = df['year_start'].fillna(pd.to_numeric(df['year_start_raw'], errors='coerce'))
    
    if 'year_end_raw' in df.columns:
        # Rellenar los nulos de year_end con year_end_raw
        df['year_end'] = df['year_end'].fillna(pd.to_numeric(df['year_end_raw'], errors='coerce'))

    # Si aún hay nulos en year_start, poner un valor por defecto (ej. 2000) para evitar error de BD
    df['year_start'] = df['year_start'].fillna(2000).astype(int)
    
    # Si year_end es nulo, asumir que sigue en producción (9999)
    df['year_end'] = df['year_end'].fillna(9999).astype(int)

    # Canonical contract aliases for SQL-first recommendation.
    df['make'] = df['brand']
    df['category'] = coalesce_columns(df, ['type', 'category']).apply(clean_string)
        
    return df


def resolve_excel_files(args: argparse.Namespace) -> List[str]:
    if args.excel_file:
        return [str(Path(path).expanduser().resolve()) for path in args.excel_file]

    raw_data_dir = Path(args.raw_data_dir).expanduser().resolve()
    return [str(raw_data_dir / filename) for filename in DEFAULT_EXCEL_FILES]


def _collect_row_skus(row: pd.Series) -> List[str]:
    sku_values: List[str] = []
    for column in row.index:
        col_lower = str(column).lower()
        value = row.get(column)
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        if 'sku' in col_lower or any(
            token in col_lower
            for token in ('wingbar', 'kit', 'foot', 'product', 'bracket', 'platform')
        ):
            sku_values.extend(parse_sku_list(value))
    return list(dict.fromkeys([sku for sku in sku_values if sku]))


def validate_fitment_quality(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if df.empty:
        issues.append(
            {
                'severity': 'critical',
                'code': 'EMPTY_DATASET',
                'message': 'No hay filas transformadas para cargar.',
                'sample_rows': [],
            }
        )
        return issues, {'rows': 0, 'rows_with_sku': 0, 'sku_coverage_percent': 0.0}

    invalid_years = df[(df['year_start'] > df['year_end']) | (df['year_start'] < 1950)]
    if not invalid_years.empty:
        issues.append(
            {
                'severity': 'critical',
                'code': 'INVALID_YEAR_RANGE',
                'message': 'Se detectaron rangos de año invalidos.',
                'sample_rows': invalid_years[['brand', 'model', 'year_start', 'year_end']]
                .head(5)
                .to_dict(orient='records'),
            }
        )

    missing_core = df[df[['make', 'model', 'category']].isna().any(axis=1)]
    if not missing_core.empty:
        issues.append(
            {
                'severity': 'critical',
                'code': 'MISSING_CANONICAL_FIELDS',
                'message': 'Faltan campos canonicos make/model/category en filas de entrada.',
                'sample_rows': missing_core[['brand', 'make', 'model', 'category']]
                .head(5)
                .to_dict(orient='records'),
            }
        )

    sku_series = df.apply(_collect_row_skus, axis=1)
    rows_with_sku = int((sku_series.apply(len) > 0).sum())
    total_rows = int(len(df))
    sku_coverage = (rows_with_sku / total_rows * 100.0) if total_rows else 0.0
    if sku_coverage < 90.0:
        issues.append(
            {
                'severity': 'critical',
                'code': 'LOW_SKU_COVERAGE',
                'message': f'Cobertura de SKU insuficiente ({sku_coverage:.2f}%).',
                'sample_rows': df[sku_series.apply(len) == 0][['brand', 'model', 'source_file', 'source_sheet']]
                .head(5)
                .to_dict(orient='records'),
            }
        )

    metrics = {
        'rows': total_rows,
        'rows_with_sku': rows_with_sku,
        'sku_coverage_percent': round(sku_coverage, 2),
    }
    return issues, metrics


def emit_quality_report(issues: List[Dict[str, Any]], metrics: Dict[str, Any]) -> None:
    emit_structured_event(
        'fitment_quality_report',
        stage='fitment_etl',
        payload={
            'metrics': metrics,
            'issues': issues,
        },
        error_code='QUALITY_CRITICAL' if any(issue.get('severity') == 'critical' for issue in issues) else None,
    )


def emit_fitment_precision_kpi(engine) -> None:
    query = text(
        """
        WITH totals AS (
            SELECT COUNT(*)::numeric AS total_vehicles
            FROM vehicles
        ),
        with_fitment AS (
            SELECT COUNT(DISTINCT vehicle_id)::numeric AS compatible_vehicles
            FROM vehicle_product_fitment
            WHERE is_compatible = TRUE
        )
        SELECT
            CASE
                WHEN t.total_vehicles = 0 THEN NULL
                ELSE ROUND((w.compatible_vehicles / t.total_vehicles) * 100, 2)
            END AS precision_percent
        FROM totals t
        CROSS JOIN with_fitment w
        """
    )
    with engine.connect() as conn:
        precision = conn.execute(query).scalar()

    emit_structured_event(
        'fitment_precision_kpi',
        stage='fitment_etl',
        payload={
            'threshold_percent': MIN_COMPATIBILITY_PRECISION_PERCENT,
            'precision_percent': float(precision) if precision is not None else None,
            'status': (
                'insufficient_data'
                if precision is None
                else ('ok' if float(precision) >= MIN_COMPATIBILITY_PRECISION_PERCENT else 'incident')
            ),
        },
        error_code='FITMENT_PRECISION_BELOW_TARGET'
        if precision is not None and float(precision) < MIN_COMPATIBILITY_PRECISION_PERCENT
        else None,
    )

def load_to_database(df, engine):
    if df.empty:
        print("No hay datos para cargar.")
        return
        
    print("Conectando a la base de datos...")
    try:
        with engine.begin() as conn:
            # 1. Insertar vehículos únicos
            print("Insertando vehículos...")
            vehicles_cols = [
                'brand',
                'make',
                'model',
                'year_start',
                'year_end',
                'type',
                'category',
                'roof_type',
                'generation',
            ]
            vehicles_df = df[[c for c in vehicles_cols if c in df.columns]].copy()

            # Asegurar columnas esperadas y normalizar para replicar COALESCE del índice único:
            # (brand, model, year_start, COALESCE(year_end,9999), COALESCE(generation,''), COALESCE(roof_type,''))
            for optional_col, default_value in [
                ('make', ''),
                ('year_end', 9999),
                ('generation', ''),
                ('roof_type', ''),
                ('type', ''),
                ('category', ''),
            ]:
                if optional_col not in vehicles_df.columns:
                    vehicles_df[optional_col] = default_value

            vehicles_df['year_end'] = pd.to_numeric(vehicles_df['year_end'], errors='coerce').fillna(9999).astype(int)
            vehicles_df['make'] = vehicles_df['make'].replace('', pd.NA).fillna(vehicles_df['brand']).astype(str).str.strip()
            vehicles_df['category'] = (
                vehicles_df['category']
                .replace('', pd.NA)
                .fillna(vehicles_df['type'])
                .astype(str)
                .str.strip()
            )
            vehicles_df['generation'] = vehicles_df['generation'].fillna('').astype(str).str.strip()
            vehicles_df['roof_type'] = vehicles_df['roof_type'].fillna('').astype(str).str.strip()
            vehicles_df['type'] = vehicles_df['type'].fillna('').astype(str).str.strip()

            unique_key_cols = ['brand', 'model', 'year_start', 'year_end', 'generation', 'roof_type']

            # IMPORTANTE: type NO forma parte del índice único, por eso deduplicamos por unique_key_cols
            vehicles_df = vehicles_df.drop_duplicates(subset=unique_key_cols, keep='first')

            print("Verificando vehículos existentes...")
            existing_vehicles = pd.read_sql(
                """
                SELECT
                    brand,
                    model,
                    year_start,
                    COALESCE(year_end, 9999) AS year_end,
                    COALESCE(generation, '') AS generation,
                    COALESCE(roof_type, '') AS roof_type
                FROM vehicles
                """,
                conn
            )
            
            if not existing_vehicles.empty:
                existing_vehicles['year_end'] = pd.to_numeric(existing_vehicles['year_end'], errors='coerce').fillna(9999).astype(int)
                existing_vehicles['generation'] = existing_vehicles['generation'].fillna('').astype(str).str.strip()
                existing_vehicles['roof_type'] = existing_vehicles['roof_type'].fillna('').astype(str).str.strip()

                # Crear clave exactamente igual a la del índice único en BD
                vehicles_df['merge_key'] = (
                    vehicles_df['brand'].astype(str) + '|' +
                    vehicles_df['model'].astype(str) + '|' +
                    vehicles_df['year_start'].astype(str) + '|' +
                    vehicles_df['year_end'].astype(str) + '|' +
                    vehicles_df['generation'] + '|' +
                    vehicles_df['roof_type']
                )
                existing_vehicles['merge_key'] = (
                    existing_vehicles['brand'].astype(str) + '|' +
                    existing_vehicles['model'].astype(str) + '|' +
                    existing_vehicles['year_start'].astype(str) + '|' +
                    existing_vehicles['year_end'].astype(str) + '|' +
                    existing_vehicles['generation'] + '|' +
                    existing_vehicles['roof_type']
                )

                # Filtrar solo los vehículos que no existen en la BD
                vehicles_df = vehicles_df[~vehicles_df['merge_key'].isin(existing_vehicles['merge_key'])]
                vehicles_df = vehicles_df.drop(columns=['merge_key'])
            
            if not vehicles_df.empty:
                print(f"Insertando {len(vehicles_df)} vehículos nuevos...")
                vehicles_df.to_sql('vehicles', conn, if_exists='append', index=False, method='multi')
                print("Vehículos insertados exitosamente.")
            else:
                print("No hay vehículos nuevos para insertar (todos ya existen en la base de datos).")

            # 2. Obtener IDs de vehículo para cargar relaciones
            vehicle_lookup = pd.read_sql(
                """
                SELECT
                    id AS vehicle_id,
                    brand,
                    model,
                    year_start,
                    COALESCE(year_end, 9999) AS year_end,
                    COALESCE(generation, '') AS generation,
                    COALESCE(roof_type, '') AS roof_type
                FROM vehicles
                """,
                conn
            )

            relation_df = df.copy()
            if 'generation' not in relation_df.columns:
                relation_df['generation'] = ''
            if 'roof_type' not in relation_df.columns:
                relation_df['roof_type'] = ''
            relation_df['year_end'] = pd.to_numeric(relation_df['year_end'], errors='coerce').fillna(9999).astype(int)
            relation_df['generation'] = relation_df['generation'].fillna('').astype(str).str.strip()
            relation_df['roof_type'] = relation_df['roof_type'].fillna('').astype(str).str.strip()

            relation_df = relation_df.merge(
                vehicle_lookup,
                on=['brand', 'model', 'year_start', 'year_end', 'generation', 'roof_type'],
                how='left'
            )
            relation_df = relation_df[relation_df['vehicle_id'].notna()].copy()
            relation_df['vehicle_id'] = relation_df['vehicle_id'].astype(int)

            # 3. Insertar fitment_kits
            print("Insertando fitment_kits...")
            fitment_kits_df = pd.DataFrame({
                'vehicle_id': relation_df['vehicle_id'],
                'foot_pack_sku': coalesce_columns(relation_df, ['foot_pack_sku', 'edge foot', 'evo foot', 'caprock foot', 'raingutter foot']).apply(extract_single_sku),
                'bar_front_sku': coalesce_columns(relation_df, ['bar_front_sku', 'wingbar edge front', 'wingbar evo', 'squarebar evo']).apply(extract_single_sku),
                'bar_rear_sku': coalesce_columns(relation_df, ['bar_rear_sku', 'wingbar edge rear']).apply(extract_single_sku),
                'kit_sku': coalesce_columns(relation_df, ['kit_sku']).apply(extract_single_sku),
                'max_load_kg': pd.to_numeric(coalesce_columns(relation_df, ['max load kg', 'max load']), errors='coerce')
            })

            fitment_kits_df = fitment_kits_df[
                fitment_kits_df[['foot_pack_sku', 'bar_front_sku', 'bar_rear_sku', 'kit_sku']].notna().any(axis=1)
            ].copy()
            fitment_kits_df = fitment_kits_df.drop_duplicates(
                subset=['vehicle_id', 'foot_pack_sku', 'bar_front_sku'],
                keep='first'
            )

            existing_kits = pd.read_sql(
                """
                SELECT
                    vehicle_id,
                    COALESCE(foot_pack_sku, '') AS foot_pack_sku,
                    COALESCE(bar_front_sku, '') AS bar_front_sku
                FROM fitment_kits
                """,
                conn
            )
            if not fitment_kits_df.empty and not existing_kits.empty:
                fitment_kits_df['merge_key'] = (
                    fitment_kits_df['vehicle_id'].astype(str) + '|' +
                    fitment_kits_df['foot_pack_sku'].fillna('') + '|' +
                    fitment_kits_df['bar_front_sku'].fillna('')
                )
                existing_kits['merge_key'] = (
                    existing_kits['vehicle_id'].astype(str) + '|' +
                    existing_kits['foot_pack_sku'].fillna('') + '|' +
                    existing_kits['bar_front_sku'].fillna('')
                )
                fitment_kits_df = fitment_kits_df[~fitment_kits_df['merge_key'].isin(existing_kits['merge_key'])]
                fitment_kits_df = fitment_kits_df.drop(columns=['merge_key'])

            if not fitment_kits_df.empty:
                fitment_kits_df.to_sql('fitment_kits', conn, if_exists='append', index=False, method='multi')
                print(f"Fitment kits insertados: {len(fitment_kits_df)}")
            else:
                print("No hay fitment_kits nuevos para insertar.")

            # 4. Construir productos y fitment por vehículo
            print("Insertando products y vehicle_product_fitment...")
            product_name_by_sku = {}
            fitment_rows = []

            note_series = coalesce_columns(relation_df, ['fitment_notes', 'notes']).apply(lambda v: None if pd.isna(v) else str(v).strip())
            engineering_series = coalesce_columns(relation_df, ['engineering_comment']).apply(lambda v: None if pd.isna(v) else str(v).strip())
            pad_series = coalesce_columns(relation_df, ['pad']).apply(lambda v: None if pd.isna(v) else str(v).strip())
            strap_col = [c for c in relation_df.columns if 'reinforcement strap' in c]
            strap_series = coalesce_columns(relation_df, strap_col).apply(parse_yes_no_bool) if strap_col else pd.Series([None] * len(relation_df), index=relation_df.index)

            base_cols = {
                'brand', 'model', 'type', 'doors', 'generation', 'year_start', 'year_end',
                'roof_type', 'vehicle_id', 'source_file', 'source_sheet', 'recommendation from',
                'car variation', 'updated', 'kit ean'
            }

            header_sku_pattern = re.compile(r'^(.*?)\s*-\s*([a-zA-Z0-9]+)$')
            sku_header_columns = {}
            for col in relation_df.columns:
                match = header_sku_pattern.match(str(col).strip())
                if match:
                    product_name = match.group(1).strip().title()
                    product_sku = normalize_sku_token(match.group(2))
                    if product_sku and len(product_sku) <= 20:
                        sku_header_columns[col] = (product_sku, product_name)
                        product_name_by_sku.setdefault(product_sku, product_name)

            keyword_cols = []
            for col in relation_df.columns:
                col_l = str(col).lower()
                if col in base_cols:
                    continue
                if col in sku_header_columns:
                    continue
                if any(k in col_l for k in [
                    'product', 'awning', 'bracket', 'platform', 'foot', 'wingbar', 'squarebar',
                    'raingutter', 'gatemate', 'instagater', 'xsporter', 'tracrac', 'gateway',
                    'passage', 'outway', 'spare', 'allax', 'kit'
                ]):
                    keyword_cols.append(col)

            for idx, row in relation_df.iterrows():
                vehicle_id = int(row['vehicle_id'])
                fitment_notes = note_series.loc[idx]
                engineering_comment = engineering_series.loc[idx]
                pad_type = pad_series.loc[idx]
                if pad_type and len(str(pad_type)) > 10:
                    pad_type = str(pad_type)[:10]
                reinforcement_strap = strap_series.loc[idx]

                for col, (sku, _) in sku_header_columns.items():
                    if is_compatible_marker(row.get(col)):
                        fitment_rows.append({
                            'vehicle_id': vehicle_id,
                            'product_sku': sku,
                            'is_compatible': True,
                            'fitment_notes': fitment_notes,
                            'pad_type': pad_type,
                            'reinforcement_strap': reinforcement_strap,
                            'engineering_comment': engineering_comment
                        })

                for col in keyword_cols:
                    skus = parse_sku_list(row.get(col))
                    if not skus:
                        continue
                    product_label = str(col).replace('_', ' ').strip().title()
                    for sku in skus:
                        if len(sku) > 20:
                            continue
                        product_name_by_sku.setdefault(sku, product_label)
                        fitment_rows.append({
                            'vehicle_id': vehicle_id,
                            'product_sku': sku,
                            'is_compatible': True,
                            'fitment_notes': fitment_notes,
                            'pad_type': pad_type,
                            'reinforcement_strap': reinforcement_strap,
                            'engineering_comment': engineering_comment
                        })

            if fitment_rows:
                vpf_df = pd.DataFrame(fitment_rows)
                vpf_df = vpf_df.drop_duplicates(subset=['vehicle_id', 'product_sku'], keep='first')

                existing_vpf = pd.read_sql(
                    """
                    SELECT vehicle_id, product_sku
                    FROM vehicle_product_fitment
                    """,
                    conn
                )
                if not existing_vpf.empty:
                    vpf_df['merge_key'] = vpf_df['vehicle_id'].astype(str) + '|' + vpf_df['product_sku']
                    existing_vpf['merge_key'] = existing_vpf['vehicle_id'].astype(str) + '|' + existing_vpf['product_sku']
                    vpf_df = vpf_df[~vpf_df['merge_key'].isin(existing_vpf['merge_key'])]
                    vpf_df = vpf_df.drop(columns=['merge_key'])
            else:
                vpf_df = pd.DataFrame(columns=[
                    'vehicle_id', 'product_sku', 'is_compatible', 'fitment_notes',
                    'pad_type', 'reinforcement_strap', 'engineering_comment'
                ])

            if product_name_by_sku:
                products_df = pd.DataFrame([
                    {'sku': sku, 'name': name or sku, 'category': 'auto_import'}
                    for sku, name in product_name_by_sku.items()
                ])
                products_df = products_df[products_df['sku'].str.len() <= 20]
                products_df = products_df.drop_duplicates(subset=['sku'], keep='first')

                existing_products = pd.read_sql("SELECT sku FROM products", conn)
                if not existing_products.empty:
                    products_df = products_df[~products_df['sku'].isin(existing_products['sku'])]

                if not products_df.empty:
                    products_df.to_sql('products', conn, if_exists='append', index=False, method='multi')
                    print(f"Productos insertados: {len(products_df)}")
                else:
                    print("No hay productos nuevos para insertar.")
            else:
                print("No se detectaron productos para insertar.")

            if not vpf_df.empty:
                vpf_df.to_sql('vehicle_product_fitment', conn, if_exists='append', index=False, method='multi')
                print(f"Relaciones vehículo-producto insertadas: {len(vpf_df)}")
            else:
                print("No hay relaciones vehículo-producto nuevas para insertar.")
            
    except Exception as e:
        print(f"Error al cargar en la base de datos: {e}")

def main(argv: Optional[Iterable[str]] = None):
    args = parse_args(argv)
    excel_files = resolve_excel_files(args)
    
    print("Iniciando proceso ETL de Thule...")
    df_raw = process_excel_files(excel_files)
    
    print("Transformando datos...")
    df_transformed = transform_data(df_raw)

    issues, metrics = validate_fitment_quality(df_transformed)
    emit_quality_report(issues, metrics)
    has_critical = any(issue['severity'] == 'critical' for issue in issues)
    if has_critical and not args.allow_quality_warnings:
        raise ValueError(
            'Carga cancelada por validaciones de calidad criticas. '
            'Use --allow-quality-warnings solo para corridas de diagnostico.'
        )
    
    try:
        engine = create_engine(build_database_uri())
        if args.run_migrations:
            run_sql_migrations(engine, args.migrations_dir)
        load_to_database(df_transformed, engine)
        emit_fitment_precision_kpi(engine)
    except Exception as e:
        print(f"Error al crear el engine de SQLAlchemy: {e}")
        
    print("Proceso ETL finalizado.")

if __name__ == "__main__":
    main()
