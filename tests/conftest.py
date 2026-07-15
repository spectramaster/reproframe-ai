from __future__ import annotations

import os
import tempfile

# Tests must never consume live provider credits or write into the real B2 bucket merely
# because a developer has a credentialed .env file in the repository checkout.
os.environ["REPROFRAME_MODE"] = "fixture"
os.environ["REPROFRAME_ARTIFACT_DIR"] = tempfile.mkdtemp(prefix="reproframe-tests-")
os.environ.pop("REPROFRAME_REVIEW_TOKEN", None)
