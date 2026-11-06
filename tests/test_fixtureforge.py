import csv
import io
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fixtureforge.generators import generate_records
from fixtureforge.models import Field, Schema
from fixtureforge.schema import SchemaError, load_schema, schema_from_data
from fixtureforge.writers import write_csv, write_json, write_new_file


def complete_schema():
    return schema_from_data({"schema_version": 1, "fields": [
        {"name": "id", "type": "sequence", "start": 100, "step": 2},
        {"name": "qty", "type": "integer", "min": -1, "max": 1},
        {"name": "kind", "type": "choice", "values": ["Widget, α", "Line\nbreak"]},
        {"name": "active", "type": "boolean"},
        {"name": "day", "type": "date", "start": "2026-01-01", "end": "2026-01-02"},
    ]})


class SchemaAndGenerationTests(unittest.TestCase):
    def test_every_type_boundaries_and_order(self):
        records = list(generate_records(complete_schema(), 20, 7))
        self.assertEqual(list(records[0]), ["id", "qty", "kind", "active", "day"])
        self.assertEqual([item["id"] for item in records], list(range(100, 140, 2)))
        self.assertTrue(all(-1 <= item["qty"] <= 1 for item in records))
        self.assertTrue(all(item["kind"] in ("Widget, α", "Line\nbreak") for item in records))
        self.assertTrue(all(type(item["active"]) is bool for item in records))
        self.assertTrue(all(item["day"] in ("2026-01-01", "2026-01-02") for item in records))

    def test_inclusive_single_value_ranges(self):
        schema = schema_from_data({"schema_version":1,"fields":[{"name":"n","type":"integer","min":5,"max":5},{"name":"d","type":"date","start":"2024-02-29","end":"2024-02-29"}]})
        self.assertEqual(list(generate_records(schema, 2, 1)), [{"n":5,"d":"2024-02-29"},{"n":5,"d":"2024-02-29"}])

    def test_reproducibility_prefix_and_global_random(self):
        schema = complete_schema(); state = random.getstate()
        long = list(generate_records(schema, 10, 42)); repeat = list(generate_records(schema, 10, 42)); short = list(generate_records(schema, 5, 42))
        self.assertEqual(long, repeat); self.assertEqual(short, long[:5]); self.assertEqual(random.getstate(), state)

    def test_schema_errors(self):
        bad = [
            {"schema_version":2,"fields":[]},
            {"schema_version":1,"fields":[]},
            {"schema_version":1,"fields":[{"name":"bad-name","type":"boolean"}]},
            {"schema_version":1,"fields":[{"name":"x","type":"boolean"},{"name":"x","type":"boolean"}]},
            {"schema_version":1,"fields":[{"name":"x","type":"unknown"}]},
            {"schema_version":1,"fields":[{"name":"x","type":"boolean","extra":1}]},
            {"schema_version":1,"fields":[{"name":"x","type":"integer","min":True,"max":2}]},
            {"schema_version":1,"fields":[{"name":"x","type":"integer","min":3,"max":2}]},
            {"schema_version":1,"fields":[{"name":"x","type":"sequence","start":1,"step":0}]},
            {"schema_version":1,"fields":[{"name":"x","type":"choice","values":[]}]},
            {"schema_version":1,"fields":[{"name":"x","type":"date","start":"2026-02-30","end":"2026-01-01"}]},
            {"schema_version":1,"fields":[{"name":"x","type":"date","start":"2026-02-01","end":"2026-01-01"}]},
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(SchemaError): schema_from_data(value)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"s.json"; path.write_text('{"schema_version":1,"schema_version":1,"fields":[]}',encoding="utf-8")
            with self.assertRaisesRegex(SchemaError,"duplicate JSON key"): load_schema(path)


class WriterTests(unittest.TestCase):
    def test_json_zero_and_values(self):
        empty=io.StringIO(); write_json([],empty); self.assertEqual(empty.getvalue(),"[]\n")
        output=io.StringIO(); write_json(iter([{"text":"雪","active":True}]),output); self.assertEqual(json.loads(output.getvalue()),[{"text":"雪","active":True}])

    def test_csv_zero_order_boolean_unicode_and_quoting(self):
        schema=complete_schema(); empty=io.StringIO(newline=""); write_csv([],schema,empty); self.assertEqual(empty.getvalue().splitlines(),["id,qty,kind,active,day"])
        output=io.StringIO(newline=""); write_csv([{"id":1,"qty":2,"kind":"Widget, α\nquoted \"x\"","active":False,"day":"2026-01-01"}],schema,output)
        row=list(csv.DictReader(io.StringIO(output.getvalue(),newline="")))[0]
        self.assertEqual(row["kind"],"Widget, α\nquoted \"x\""); self.assertEqual(row["active"],"false"); self.assertEqual(list(row),["id","qty","kind","active","day"])

    def test_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"out.json"; path.write_text("sentinel",encoding="utf-8")
            with self.assertRaises(FileExistsError): write_new_file(path,[],complete_schema(),"json")
            self.assertEqual(path.read_text(),"sentinel")

    def test_failed_write_cleanup(self):
        class Broken:
            def __iter__(self):
                yield {"id":1}
                raise OSError("synthetic failure")
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"out.json"
            with self.assertRaisesRegex(OSError,"synthetic failure"): write_new_file(path,Broken(),complete_schema(),"json")
            self.assertFalse(path.exists())


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name); self.schema=self.root/"schema.json"
        data={"schema_version":1,"fields":[{"name":"id","type":"sequence","start":1,"step":1},{"name":"active","type":"boolean"}]}; self.schema.write_text(json.dumps(data),encoding="utf-8")
        env=os.environ.copy(); src=Path(__file__).resolve().parents[1]; env["PYTHONPATH"]=str(src)+((os.pathsep+env["PYTHONPATH"]) if env.get("PYTHONPATH") else ""); self.env=env
    def tearDown(self): self.temp.cleanup()
    def run_cli(self,*args): return subprocess.run([sys.executable,"-m","fixtureforge",*map(str,args)],cwd=self.root,env=self.env,text=True,encoding="utf-8",capture_output=True)
    def test_commands_formats_and_exit_codes(self):
        self.assertEqual(self.run_cli("validate",self.schema).returncode,0); self.assertEqual(self.run_cli("describe",self.schema,"--format","json").returncode,0)
        preview=self.run_cli("preview",self.schema,"--rows",3,"--seed",42,"--format","json"); self.assertEqual(preview.returncode,0); self.assertEqual(len(json.loads(preview.stdout)),3)
        out=self.root/"out.csv"; made=self.run_cli("generate",self.schema,"--rows",0,"--seed",42,"--format","csv","--output",out); self.assertEqual(made.returncode,0); self.assertEqual(out.read_text().strip(),"id,active")
        conflict=self.run_cli("generate",self.schema,"--rows",1,"--seed",1,"--format","csv","--output",out); self.assertEqual(conflict.returncode,2)
    def test_invalid_schema_exit_one_creates_no_output(self):
        bad=self.root/"bad.json"; bad.write_text('{"schema_version":1,"fields":[]}',encoding="utf-8"); output=self.root/"never.json"
        result=self.run_cli("generate",bad,"--rows",1,"--seed",1,"--format","json","--output",output); self.assertEqual(result.returncode,1); self.assertFalse(output.exists()); self.assertNotIn("Traceback",result.stderr)
        report=self.run_cli("validate",bad,"--format","json"); self.assertEqual(report.returncode,1); self.assertFalse(json.loads(report.stdout)["valid"])
    def test_invalid_arguments_exit_two(self):
        self.assertEqual(self.run_cli("preview",self.schema,"--rows",-1,"--seed",1,"--format","json").returncode,2)


if __name__ == "__main__": unittest.main()
