"""Package entry point; dispatch the optional OSM discovery command."""
import sys

if len(sys.argv) > 1 and sys.argv[1] == "osm-search":
    from .osm_cli import main
    raise SystemExit(main(sys.argv[2:]))

from .cli import main
raise SystemExit(main())
