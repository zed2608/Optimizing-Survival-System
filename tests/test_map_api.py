import tempfile
import unittest
from pathlib import Path
from backend.app import app

class MapApiTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/"points.csv"
        self.original=app.config["POINTS_CSV"]
        app.config["POINTS_CSV"]=str(self.path)
        self.client=app.test_client()
    def tearDown(self):
        app.config["POINTS_CSV"]=self.original
        self.directory.cleanup()
    def test_missing_dataset(self):
        self.assertEqual(self.client.get("/api/points").status_code,503)
    def test_missing_coordinates(self):
        self.path.write_text("soil_type\n4478\n",encoding="utf-8")
        self.assertEqual(self.client.get("/api/points").status_code,422)
    def test_existing_transform(self):
        self.path.write_text("x,y,soil_type,slope_1\n121.1,14.7,4478,45\n",encoding="utf-8")
        result=self.client.get("/api/points")
        self.assertEqual(result.status_code,200)
        row=result.get_json()[0]
        self.assertEqual(row["soil_type"],"Gleyic Cambisol (Clay-Loam)")
        self.assertEqual(row["slope_1"],45)
        self.assertAlmostEqual(row["left"],121.1-0.000015)
