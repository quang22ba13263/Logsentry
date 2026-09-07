from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from evaluation.adapters.hdfs_adapter import load_hdfs_traces, parse_event_sequence

class HdfsAdapterTests(unittest.TestCase):
    def test_parse_sequence(self):
        self.assertEqual(("E1", "E29"), parse_event_sequence("[E1,E29]"))
        with self.assertRaises(ValueError): parse_event_sequence("E1,E2")
    def test_join_excludes_ids_labels_and_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); traces=root/'t.csv'; occurrence=root/'o.csv'; labels=root/'l.csv'
            traces.write_text('BlockId,Label,Type,Features\nb1,Success,,"[E1,E2]"\n', encoding='utf-8')
            occurrence.write_text('BlockId,Label,Type,E1,E2\nb1,Success,,1,2\n', encoding='utf-8')
            labels.write_text('BlockId,Label\nb1,Anomaly\n', encoding='utf-8')
            item=load_hdfs_traces(traces,occurrence,labels)[0]
            self.assertEqual(1,item.ground_truth); self.assertEqual({'E1':1.0,'E2':2.0},item.features)
            self.assertNotIn('BlockId',item.features); self.assertNotIn('Label',item.features); self.assertNotIn('Type',item.features)
