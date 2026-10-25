from __future__ import annotations

import json
import os
import struct
import unittest

import numpy as np
from fastapi import Request
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from staff_galaxy import api
from staff_galaxy.graph_buffers import HEADER_SIZE, MAGIC, SEGMENT_NAMES, parse_segment_table
from staff_galaxy.graph_db import clear_database, create_constraints, read, record_data_snapshot, set_driver, write_batches
from staff_galaxy.ingest import credit_row, write_anime, write_credits, write_persons, write_positions
from staff_galaxy.search_index import build_person_search_terms
from staff_galaxy.visible_edges import benjamini_hochberg, build_visible_person_edges, fit_bicm


# The suite wipes this instance; start it with `docker compose --profile test up -d`.
TEST_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7688")
TEST_AUTH = ("neo4j", os.environ.get("NEO4J_TEST_PASSWORD", "staff-galaxy-test"))


def _get_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({"type": "http", "method": "GET", "headers": headers or []})


def setUpModule() -> None:
    global _driver
    if TEST_URI == os.environ.get("NEO4J_URI"):
        raise RuntimeError("NEO4J_TEST_URI must not point at the main graph; the tests wipe it")
    _driver = GraphDatabase.driver(TEST_URI, auth=TEST_AUTH)
    try:
        _driver.verify_connectivity()
    except ServiceUnavailable as exc:
        _driver.close()
        raise unittest.SkipTest(f"Neo4j test instance not reachable at {TEST_URI}") from exc
    _build_graph(_driver)
    set_driver(_driver)


def tearDownModule() -> None:
    set_driver(None)
    _driver.close()


def _build_graph(driver) -> None:
    clear_database(driver)
    create_constraints(driver)
    write_persons(
        driver,
        [
            {
                "id": 1,
                "name": "宮崎駿",
                "infobox": "{{Infobox Crt\r\n|简体中文名= 宫崎骏\r\n|繁體中文名= 宮崎駿\r\n|别名={\r\n[照樹務]\r\n[英文名|Hayao Miyazaki]\r\n[日文名|宮崎 駿]\r\n[纯假名|みやざき はやお]\r\n[罗马字|Miyazaki Hayao]\r\n}\r\n}}",
                "career_json": "[]",
                "summary": "",
            },
            {"id": 2, "name": "Hidden Collaborator", "infobox": "{{Infobox Crt\r\n|繁體中文名= 隱藏合作者\r\n}}", "career_json": "[]", "summary": ""},
            {"id": 3, "name": "Visible Bridge", "infobox": "", "career_json": "[]", "summary": ""},
            {"id": 4, "name": "Hidden Endpoint", "infobox": "", "career_json": "[]", "summary": ""},
        ],
    )
    write_anime(
        driver,
        [
            {"id": 10, "name": "Hidden Work", "name_cn": "隐藏作品", "date": "2020-01-01", "year": 2020},
            {"id": 11, "name": "Visible Work", "name_cn": "可见作品", "date": "2021-01-01", "year": 2021},
            {"id": 12, "name": "Hidden Bridge Work", "name_cn": "隐藏桥接作品", "date": "2022-01-01", "year": 2022},
        ],
    )
    positions = {
        1: {"position_id": 1, "cn": "原画", "en": "Key Animation", "jp": "原画", "normalized_role": "key_animation", "role_tier": "D", "role_weight": 3.0},
        2: {"position_id": 2, "cn": "脚本", "en": "Script", "jp": "脚本", "normalized_role": "script", "role_tier": "B", "role_weight": 12.0},
    }
    write_positions(driver, positions.values())
    write_credits(
        driver,
        [
            credit_row(subject_id, person_id, position_id, "", positions)
            for subject_id, person_id, position_id in [
                (10, 1, 1),
                (10, 2, 1),
                (11, 1, 2),
                (11, 3, 2),
                (12, 3, 1),
                (12, 4, 1),
            ]
        ],
    )
    write_batches(
        driver,
        """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.id})
        SET p:GalaxyNode, p.community_id = 0, p.x = row.x, p.y = 0.0,
            p.visible_degree = row.degree, p.visible_weighted_degree = row.weighted,
            p.node_size = row.size, p.role_layer = 'test', p.layout_method = 'fixture'
        """,
        [
            {"id": 1, "x": 0.0, "degree": 10, "weighted": 100.0, "size": 6.0},
            {"id": 2, "x": 1.0, "degree": 1, "weighted": 3.0, "size": 3.0},
            {"id": 3, "x": 2.0, "degree": 5, "weighted": 12.0, "size": 4.0},
            {"id": 4, "x": 3.0, "degree": 1, "weighted": 3.0, "size": 3.0},
        ],
    )
    build_visible_person_edges(driver, min_role_weight=12.0)
    build_person_search_terms(driver)
    record_data_snapshot(
        driver,
        archive_name="dump-test.zip",
        archive_created_at="2026-05-19T21:04:35Z",
        archive_size_bytes=1234,
        source_url="https://example.test/dump-test.zip",
    )


class CompleteGraphApiTests(unittest.TestCase):
    def test_complete_edge_is_queryable_when_not_visible(self) -> None:
        visible = read(
            _driver,
            "MATCH (:Person {id: 1})-[e:COLLAB]-(:Person {id: 2}) RETURN count(e) AS n",
        )[0]["n"]

        self.assertEqual(visible, 0)

        # One shared work is never BiCM-significant; the 1-3 tie survives only
        # as the strongest edge of the spanning forest.
        reason = read(
            _driver,
            "MATCH (:Person {id: 1})-[e:COLLAB]-(:Person {id: 3}) RETURN e.selection_reason AS r",
        )[0]["r"]
        self.assertEqual(reason, "spanning_forest")

        detail = api.collaboration_detail(1, 2)
        self.assertEqual(detail["selectionReason"], "all_staff")
        self.assertEqual(detail["sharedWorksCount"], 1)
        self.assertEqual(detail["sharedWorks"][0]["subjectId"], 10)
        self.assertEqual(detail["sharedWorks"][0]["personARoles"], "原画")
        self.assertEqual(detail["sharedWorks"][0]["personBRoles"], "原画")
        self.assertEqual(detail["personA"]["nameCn"], "宫崎骏")
        self.assertEqual(detail["personA"]["nameTw"], "宮崎駿")
        self.assertEqual(detail["source"]["snapshot"]["archiveName"], "dump-test.zip")

    def test_path_uses_complete_edges_not_visible_edges(self) -> None:
        result = api.shortest_path(1, 4, max_paths=3, max_depth=3)

        self.assertTrue(result["found"])
        self.assertEqual(result["degree"], 2)
        self.assertEqual(result["paths"][0]["nodes"], ["1", "3", "4"])
        self.assertEqual(result["paths"][0]["steps"][1]["sharedWorksCount"], 1)

    def test_search_prioritizes_numeric_id_and_cjk_variant(self) -> None:
        by_id = api.search_persons(q="1", limit=3)
        by_variant = api.search_persons(q="宫崎骏", limit=3)
        by_romanized = api.search_persons(q="Hayao Miyazaki", limit=3)
        by_alias = api.search_persons(q="照樹務", limit=3)
        by_traditional = api.search_persons(q="隱藏合作者", limit=3)
        by_romanized_typo = api.search_persons(q="Miyazki Hayao", limit=3)
        by_cjk_typo = api.search_persons(q="宫崎俊", limit=3)

        self.assertEqual(by_id[0]["id"], "1")
        self.assertEqual(by_variant[0]["id"], "1")
        self.assertEqual(by_variant[0]["name"], "宮崎駿")
        self.assertEqual(by_variant[0]["nameCn"], "宫崎骏")
        self.assertEqual(by_variant[0]["nameTw"], "宮崎駿")
        self.assertEqual(by_romanized[0]["id"], "1")
        self.assertEqual(by_alias[0]["id"], "1")
        self.assertEqual(by_traditional[0]["id"], "2")
        self.assertEqual(by_traditional[0]["nameTw"], "隱藏合作者")
        self.assertEqual(by_romanized_typo[0]["id"], "1")
        self.assertEqual(by_cjk_typo[0]["id"], "1")

    def test_manifest_returns_data_snapshot(self) -> None:
        manifest = api.manifest()

        self.assertEqual(manifest["version"], 2)
        self.assertEqual(manifest["snapshot"]["archiveName"], "dump-test.zip")
        self.assertEqual(manifest["snapshot"]["archiveCreatedAt"], "2026-05-19T21:04:35Z")
        self.assertEqual(manifest["snapshot"]["archiveSizeBytes"], 1234)
        self.assertEqual(manifest["snapshot"]["sourceUrl"], "https://example.test/dump-test.zip")
        self.assertEqual(manifest["graph"]["nodes"], 4)
        self.assertEqual(manifest["graph"]["edges"], 1)

    def test_graph_buffers_roundtrip(self) -> None:
        response = api.graph_buffers(_get_request())
        payload = response.body

        self.assertEqual(response.media_type, "application/octet-stream")
        self.assertEqual(payload[:4], MAGIC)
        _, version, node_count, edge_count = struct.unpack_from("<4sIII", payload, 0)
        self.assertEqual(version, 2)
        self.assertEqual(node_count, 4)
        self.assertEqual(edge_count, 1)

        table = parse_segment_table(payload)
        self.assertEqual(tuple(table), SEGMENT_NAMES)
        # 4-byte alignment lets the frontend construct typed-array views directly.
        self.assertTrue(all(offset % 4 == 0 for offset, _ in table.values()))
        self.assertEqual(table["positions"], (HEADER_SIZE, 8))
        self.assertEqual(table["sizes"][1], 4)
        self.assertEqual(table["colors"][1], 16)
        self.assertEqual(table["community"][1], 4)
        self.assertEqual(table["edgePairs"][1], 2)
        self.assertEqual(table["edgeWeights"][1], 1)
        self.assertEqual(table["edgeShared"][1], 1)

        # Edge (1, 3) — the only visible edge — must reference meta index order.
        meta = json.loads(api.graph_meta(_get_request()).body)
        index_of = {node["id"]: i for i, node in enumerate(meta["nodes"])}
        offset = table["edgePairs"][0]
        source_index, target_index = struct.unpack_from("<II", payload, offset)
        self.assertEqual({source_index, target_index}, {index_of["1"], index_of["3"]})

        # Positions are normalized into the 8192 Cosmos space.
        pos_offset = table["positions"][0]
        coords = struct.unpack_from(f"<{node_count * 2}f", payload, pos_offset)
        self.assertTrue(all(0.0 <= v <= 8192.0 for v in coords))

    def test_graph_buffers_etag_revalidation(self) -> None:
        first = api.graph_buffers(_get_request())
        etag = first.headers["ETag"]
        self.assertIn("immutable", first.headers["Cache-Control"])

        second = api.graph_buffers(_get_request([(b"if-none-match", etag.encode())]))
        self.assertEqual(second.status_code, 304)

    def test_graph_and_path_return_person_name_variants(self) -> None:
        meta_response = api.graph_meta(_get_request())
        nodes = json.loads(meta_response.body)["nodes"]
        center = api.person_galaxy(1)
        path = api.shortest_path(1, 4, max_paths=3, max_depth=3)

        self.assertEqual(nodes[0]["nameCn"], "宫崎骏")
        self.assertEqual(nodes[0]["nameTw"], "宮崎駿")
        self.assertEqual(center["nodes"][0]["nameCn"], "宫崎骏")
        self.assertEqual(center["nodes"][0]["nameTw"], "宮崎駿")
        visible_neighbor = next(node for node in center["nodes"] if node["id"] == "3")
        self.assertEqual(visible_neighbor["neighborRoleTier"], "B")
        self.assertEqual(
            next(person for person in path["people"] if person["id"] == "1")["nameCn"],
            "宫崎骏",
        )
        self.assertEqual(
            next(person for person in path["people"] if person["id"] == "1")["nameTw"],
            "宮崎駿",
        )

    def test_person_detail_returns_stats_roles_and_recent_works(self) -> None:
        detail = api.person_detail(1)

        self.assertEqual(detail["person"]["id"], "1")
        self.assertEqual(detail["person"]["name"], "宮崎駿")
        self.assertEqual(detail["person"]["nameCn"], "宫崎骏")
        self.assertEqual(detail["person"]["nameTw"], "宮崎駿")
        self.assertEqual(detail["stats"]["animeSubjectCount"], 2)
        self.assertEqual(detail["stats"]["firstCreditYear"], 2020)
        self.assertEqual(detail["stats"]["latestCreditYear"], 2021)
        self.assertEqual(
            {role["position"] for role in detail["topRoles"]},
            {"原画", "脚本"},
        )
        self.assertEqual(detail["recentWorks"][0]["subjectId"], 11)
        self.assertEqual(detail["recentWorks"][0]["roles"], "脚本")
        self.assertEqual(detail["source"]["snapshot"]["archiveName"], "dump-test.zip")

    def test_person_credits_returns_complete_raw_role_rows(self) -> None:
        credits = api.person_credits(1)

        self.assertEqual(credits["person"]["id"], "1")
        self.assertEqual(credits["person"]["name"], "宮崎駿")
        self.assertEqual(credits["person"]["nameTw"], "宮崎駿")
        self.assertEqual(credits["total"], 2)
        self.assertEqual([row["subjectId"] for row in credits["credits"]], [11, 10])
        self.assertEqual(credits["credits"][0]["rawPosition"], "脚本")
        self.assertEqual(credits["credits"][0]["normalizedRole"], "script")
        self.assertEqual(credits["credits"][0]["roleTier"], "B")
        self.assertEqual(credits["credits"][1]["rawPosition"], "原画")
        self.assertEqual(credits["credits"][1]["normalizedRole"], "key_animation")
        self.assertEqual(credits["source"]["snapshot"]["archiveName"], "dump-test.zip")


class BackboneStatisticsTests(unittest.TestCase):
    def test_bicm_reproduces_both_degree_sequences(self) -> None:
        rng = np.random.default_rng(0)
        incidence = rng.random((60, 40)) < rng.random((60, 1)) * rng.random((1, 40))
        incidence[:, 0] = incidence[0, :] = True  # no empty rows/columns
        rows, cols = incidence.sum(axis=1), incidence.sum(axis=0)

        row_class, col_mult, P = fit_bicm(rows, cols)
        _, col_class = np.unique(cols, return_inverse=True)
        full = P[row_class][:, col_class]

        np.testing.assert_allclose(full.sum(axis=1), rows, rtol=1e-8)
        np.testing.assert_allclose(full.sum(axis=0), cols, rtol=1e-8)

    def test_benjamini_hochberg_counts_untested_pairs(self) -> None:
        log_p = np.log(np.array([0.001, 0.01, 0.03, 0.5]))

        # With only the 4 observed tests, p <= 0.05 * rank / 4 keeps the first three ...
        self.assertEqual(benjamini_hochberg(log_p, 0.05, 4).tolist(), [True, True, True, False])
        # ... but across 40 hypotheses (36 unobserved, p = 1) only p <= 0.05 * rank / 40 survives.
        self.assertEqual(benjamini_hochberg(log_p, 0.05, 40).tolist(), [True, False, False, False])

    def test_bicm_degenerate_graph_has_exact_solution(self) -> None:
        # Complete bipartite K(2,1): the only consistent probabilities are 1.
        row_class, _, P = fit_bicm(np.array([1, 1]), np.array([2]))

        self.assertEqual(P[row_class].tolist(), [[1.0], [1.0]])


if __name__ == "__main__":
    unittest.main()
