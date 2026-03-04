# ─────────────────────────────────────────────
#  neo4j_db/queries.py  –  Requêtes Cypher
#  Schéma réel vérifié sur la base Neo4j
# ─────────────────────────────────────────────
#
#  Nœuds (:Building)
#    building_id, iris_code, type, address,
#    iris_name, longitude, latitude,
#    annual_consumption_kwh, annual_production_kwh
#
#  Nœuds (:Period)
#    period_id, start_time, end_time, time_step
#
#  Nœuds (:Supplier)
#    supplier_id, name, buy_price
#
#  Relations :
#    (Building)-[:HAS_DISTANCE {distance_m}]->(Building)
#    (Building)-[:HAS_ENERGY_DATA {kwh_consumed, kwh_produced, co2_cost}]->(Period)
#    (Supplier)-[:HAS_CONTRACT {contract_id, tarif_type, price_by_kwh, start_date, end_date}]->(Building)
#    (Building)-[:CONNECTED_TO]->(LineBT)
#    (LineBT)-[:FED_BY]->(ElectricSubstation)
#    (Building)-[:PART_OF]->(Grid)
# ─────────────────────────────────────────────


# ══════════════════════════════════════════════
#  1. BÂTIMENTS
# ══════════════════════════════════════════════

def get_all_buildings(driver) -> list[dict]:
    query = """
    MATCH (b:Building)
    RETURN
        b.building_id            AS building_id,
        b.address                AS address,
        b.iris_code              AS iris_code,
        b.iris_name              AS iris_name,
        b.type                   AS type,
        b.latitude               AS lat,
        b.longitude              AS lon,
        b.annual_consumption_kwh AS consommation,
        b.annual_production_kwh  AS production
    ORDER BY b.building_id
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query)]


def get_buildings_by_iris(driver, iris_code: str) -> list[dict]:
    query = """
    MATCH (b:Building {iris_code: $iris_code})
    RETURN
        b.building_id            AS building_id,
        b.address                AS address,
        b.iris_code              AS iris_code,
        b.iris_name              AS iris_name,
        b.type                   AS type,
        b.latitude               AS lat,
        b.longitude              AS lon,
        b.annual_consumption_kwh AS consommation,
        b.annual_production_kwh  AS production
    ORDER BY b.building_id
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query, iris_code=iris_code)]


def get_producers(driver) -> list[dict]:
    """Bâtiments ayant une production annuelle > 0."""
    query = """
    MATCH (b:Building)
    WHERE b.annual_production_kwh IS NOT NULL AND b.annual_production_kwh > 0
    RETURN
        b.building_id            AS building_id,
        b.address                AS address,
        b.iris_name              AS iris_name,
        b.latitude               AS lat,
        b.longitude              AS lon,
        b.annual_production_kwh  AS production
    ORDER BY b.annual_production_kwh DESC
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query)]


def get_zones_iris(driver) -> list[dict]:
    query = """
    MATCH (b:Building)
    WHERE b.iris_code IS NOT NULL
    RETURN DISTINCT b.iris_code AS iris_code, b.iris_name AS iris_name
    ORDER BY iris_name
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query)]


def get_stats_globales(driver) -> dict:
    query = """
    MATCH (b:Building)
    RETURN
        count(b)                                                    AS nb_batiments,
        sum(b.annual_consumption_kwh)                               AS conso_totale_kwh,
        sum(b.annual_production_kwh)                                AS prod_totale_kwh,
        count(CASE WHEN b.annual_production_kwh > 0 THEN 1 END)    AS nb_producteurs
    """
    with driver.session() as session:
        return session.run(query).single().data()


# ══════════════════════════════════════════════
#  2. DISTANCES
# ══════════════════════════════════════════════

def get_distances(driver, iris_code: str = None) -> list[dict]:
    if iris_code:
        query = """
        MATCH (a:Building {iris_code: $iris_code})-[r:HAS_DISTANCE]->(b:Building)
        RETURN
            a.building_id  AS from_id,
            b.building_id  AS to_id,
            r.distance_m   AS metres
        """
        params = {"iris_code": iris_code}
    else:
        query = """
        MATCH (a:Building)-[r:HAS_DISTANCE]->(b:Building)
        RETURN
            a.building_id  AS from_id,
            b.building_id  AS to_id,
            r.distance_m   AS metres
        """
        params = {}

    with driver.session() as session:
        return [r.data() for r in session.run(query, **params)]


def get_voisins_dans_rayon(driver, building_id: str, rayon_m: float) -> list[dict]:
    query = """
    MATCH (a:Building {building_id: $building_id})-[r:HAS_DISTANCE]->(b:Building)
    WHERE r.distance_m <= $rayon
    RETURN
        b.building_id            AS building_id,
        b.address                AS address,
        b.latitude               AS lat,
        b.longitude              AS lon,
        b.annual_consumption_kwh AS consommation,
        b.annual_production_kwh  AS production,
        r.distance_m             AS distance_m
    ORDER BY r.distance_m
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query, building_id=building_id, rayon=rayon_m)]


# ══════════════════════════════════════════════
#  3. DONNÉES TEMPORELLES
# ══════════════════════════════════════════════

def get_energie_par_periode(driver, building_id: str) -> list[dict]:
    query = """
    MATCH (b:Building {building_id: $building_id})-[e:HAS_ENERGY_DATA]->(p:Period)
    RETURN
        p.period_id    AS period_id,
        p.start_time   AS start_time,
        p.end_time     AS end_time,
        p.time_step    AS time_step,
        e.kwh_consumed AS kwh_consumed,
        e.kwh_produced AS kwh_produced,
        e.co2_cost     AS co2_cost
    ORDER BY p.start_time
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query, building_id=building_id)]


# ══════════════════════════════════════════════
#  4. FOURNISSEURS & CONTRATS
# ══════════════════════════════════════════════

def get_suppliers(driver) -> list[dict]:
    query = """
    MATCH (s:Supplier)
    RETURN s.supplier_id AS supplier_id, s.name AS name, s.buy_price AS buy_price
    ORDER BY s.name
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query)]


def get_contrat_batiment(driver, building_id: str) -> dict:
    query = """
    MATCH (s:Supplier)-[c:HAS_CONTRACT]->(b:Building {building_id: $building_id})
    RETURN
        s.name         AS fournisseur,
        s.buy_price    AS buy_price,
        c.contract_id  AS contract_id,
        c.tarif_type   AS tarif_type,
        c.price_by_kwh AS price_by_kwh,
        c.start_date   AS start_date,
        c.end_date     AS end_date
    """
    with driver.session() as session:
        record = session.run(query, building_id=building_id).single()
        return record.data() if record else {}


# ══════════════════════════════════════════════
#  5. GRIDS
# ══════════════════════════════════════════════

def get_grids(driver) -> list[dict]:
    query = """
    MATCH (b:Building)-[:PART_OF]->(g:Grid)
    RETURN
        g.grid_id           AS grid_id,
        g.nb_buildings      AS nb_buildings,
        g.radius            AS radius,
        g.local_usage_ratio AS local_usage_ratio,
        g.prix_avantage     AS prix_avantage,
        collect(b.building_id) AS membres
    ORDER BY g.grid_id
    """
    with driver.session() as session:
        return [r.data() for r in session.run(query)]


def importer_resultats_grids(driver, grids: list[dict]):
    query_grid = """
    MERGE (g:Grid {grid_id: $grid_id})
    SET
        g.nb_buildings      = $nb_buildings,
        g.radius            = $rayon_effectif,
        g.local_usage_ratio = $local_usage_ratio,
        g.prix_avantage     = $prix_avantage
    """
    query_relation = """
    MATCH (b:Building {building_id: $building_id})
    MATCH (g:Grid {grid_id: $grid_id})
    MERGE (b)-[:PART_OF]->(g)
    """
    with driver.session() as session:
        for grid in grids:
            session.run(query_grid,
                        grid_id=grid["grid_id"],
                        nb_buildings=len(grid["membres"]),
                        rayon_effectif=grid["rayon_effectif"],
                        local_usage_ratio=grid["local_usage_ratio"],
                        prix_avantage=grid["prix_avantage"])
            for bat_id in grid["membres"]:
                session.run(query_relation,
                            building_id=bat_id,
                            grid_id=grid["grid_id"])