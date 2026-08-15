from __future__ import annotations

import argparse
import json

from src.knowledge.drive_source import DriveSourceClient
from src.knowledge.private_config import PrivateKnowledgeConfig
from src.knowledge.private_sync import PrivateKnowledgeSync


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize allowlisted private Google Drive knowledge into Pinecone"
    )
    parser.add_argument("--dry-run", action="store_true", help="scan only; do not download or write")
    args = parser.parse_args()

    config = PrivateKnowledgeConfig.from_env()
    if not config.enabled:
        print("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE is not configured")
        return 2

    sync = PrivateKnowledgeSync(config, DriveSourceClient())
    report = sync.sync(dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "scanned": report.scanned,
                "skipped": report.skipped,
                "updated": report.updated,
                "deleted": report.deleted,
                "failed": report.failed,
                "failed_doc_ids": report.failed_doc_ids,
            },
            indent=2,
        )
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
