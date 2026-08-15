from src.knowledge import private_ingest as ingest
from src.knowledge.private_models import PrivateSourceMetadata


class FakeIndex:
    def __init__(self, fail_upsert=False, fail_on_upsert_call=None):
        self.fail_upsert = fail_upsert
        self.fail_on_upsert_call = fail_on_upsert_call
        self.upserts = []
        self.deletes = []
        self.upsert_calls = 0
