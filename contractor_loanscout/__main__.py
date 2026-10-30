"""Package entry point for the existing DOT workflow and optional OSM tools."""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "osm-search":
    from .osm_cli import main
    raise SystemExit(main(sys.argv[2:]))

if len(sys.argv) > 1 and sys.argv[1] == "email-enrich":
    from .email_cli import main
    raise SystemExit(main(sys.argv[2:]))

if len(sys.argv) > 1 and sys.argv[1] == "dedupe":
    from .dedupe_cli import main
    raise SystemExit(main(sys.argv[2:]))

if len(sys.argv) > 1 and sys.argv[1] == "master-update":
    from .master_cli import main
    raise SystemExit(main(sys.argv[2:]))

from .cli import main
raise SystemExit(main())
