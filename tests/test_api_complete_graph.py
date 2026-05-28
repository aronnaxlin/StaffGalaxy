from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from staff_galaxy import api
from staff_galaxy.database import (
    connect_database,
    create_indexes,
    create_schema,
    create_supporting_views,
    record_data_snapshot,
)
from staff_galaxy.search_index import build_person_search_terms
from staff_galaxy.visible_edges import build_person_collaboration_edges, build_visible_person_edges


class CompleteGraphApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_db = os.environ.get("STAFF_GALAXY_DB")
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "staff_galaxy_test.duckdb"
        self._build_database()
        os.environ["STAFF_GALAXY_DB"] = str(self.db_path)

    def tearDown(self) -> None:
        if self._old_db is None:
            os.environ.pop("STAFF_GALAXY_DB", None)
        else:
            os.environ["STAFF_GALAXY_DB"] = self._old_db
        self._tmp.cleanup()

    def _build_database(self) -> None:
        conn = connect_database(self.db_path)
        try:
            create_schema(conn)
            conn.executemany(
                "INSERT INTO persons VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        1,
                        "宮崎駿",
                        1,
                        "{{Infobox Crt\r\n|简体中文名= 宫崎骏\r\n|繁體中文名= 宮崎駿\r\n|别名={\r\n[照樹務]\r\n[英文名|Hayao Miyazaki]\r\n[日文名|宮崎 駿]\r\n[纯假名|みやざき はやお]\r\n[罗马字|Miyazaki Hayao]\r\n}\r\n}}",
                        "[]",
                        "",
                    ),
                    (2, "Hidden Collaborator", 1, "{{Infobox Crt\r\n|繁體中文名= 隱藏合作者\r\n}}", "[]", ""),
                    (3, "Visible Bridge", 1, "", "[]", ""),
                    (4, "Hidden Endpoint", 1, "", "[]", ""),
                ],
            )
            conn.executemany(
                "INSERT INTO subjects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (10, 2, "Hidden Work", "隐藏作品", "2020-01-01", 2020, None, None, None),
                    (11, 2, "Visible Work", "可见作品", "2021-01-01", 2021, None, None, None),
                    (12, 2, "Hidden Bridge Work", "隐藏桥接作品", "2022-01-01", 2022, None, None, None),
                ],
            )
            conn.executemany(
                "INSERT INTO staff_positions VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, "原画", "Key Animation", "原画", "key_animation", "D", 3.0),
                    (2, "脚本", "Script", "脚本", "script", "B", 12.0),
                ],
            )
            conn.executemany(
                "INSERT INTO credits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (10, 1, 1, "原画", "原画", "Key Animation", "原画", "key_animation", "D", 3.0, ""),
                    (10, 2, 1, "原画", "原画", "Key Animation", "原画", "key_animation", "D", 3.0, ""),
                    (11, 1, 2, "脚本", "脚本", "Script", "脚本", "script", "B", 12.0, ""),
                    (11, 3, 2, "脚本", "脚本", "Script", "脚本", "script", "B", 12.0, ""),
                    (12, 3, 1, "原画", "原画", "Key Animation", "原画", "key_animation", "D", 3.0, ""),
                    (12, 4, 1, "原画", "原画", "Key Animation", "原画", "key_animation", "D", 3.0, ""),
                ],
            )
            conn.executemany(
                "INSERT INTO graph_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, 0, 0.0, 0.0, 10, 100.0, 6.0, "test", "fixture"),
                    (2, 0, 1.0, 0.0, 1, 3.0, 3.0, "test", "fixture"),
                    (3, 0, 2.0, 0.0, 5, 12.0, 4.0, "test", "fixture"),
                    (4, 0, 3.0, 0.0, 1, 3.0, 3.0, "test", "fixture"),
                ],
            )
            build_person_collaboration_edges(conn)
            build_visible_person_edges(conn, min_role_weight=12.0, top_k=10)
            build_person_search_terms(conn)
            create_supporting_views(conn)
            create_indexes(conn)
            record_data_snapshot(
                conn,
                archive_name="dump-test.zip",
                archive_created_at="2026-05-19T21:04:35Z",
                archive_size_bytes=1234,
                source_url="https://example.test/dump-test.zip",
            )
        finally:
            conn.close()

    def test_complete_edge_is_queryable_when_not_visible(self) -> None:
        with api.connect_readonly() as conn:
            visible = conn.execute(
                """
                SELECT COUNT(*)
                FROM visible_person_edges
                WHERE source_person_id = 1 AND target_person_id = 2
                """
            ).fetchone()[0]

        self.assertEqual(visible, 0)

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

        self.assertEqual(manifest["snapshot"]["archiveName"], "dump-test.zip")
        self.assertEqual(manifest["snapshot"]["archiveCreatedAt"], "2026-05-19T21:04:35Z")
        self.assertEqual(manifest["snapshot"]["archiveSizeBytes"], 1234)
        self.assertEqual(manifest["snapshot"]["sourceUrl"], "https://example.test/dump-test.zip")

    def test_graph_and_path_return_person_name_variants(self) -> None:
        nodes = api.graph_nodes("global")
        center = api.person_galaxy(1)
        path = api.shortest_path(1, 4, max_paths=3, max_depth=3)

        self.assertEqual(nodes[0]["nameCn"], "宫崎骏")
        self.assertEqual(nodes[0]["nameTw"], "宮崎駿")
        self.assertEqual(center["nodes"][0]["nameCn"], "宫崎骏")
        self.assertEqual(center["nodes"][0]["nameTw"], "宮崎駿")
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


if __name__ == "__main__":
    unittest.main()
