{
    "name": "Replica Reporter (Env-configured)",
    "version": "15.0.1.0.0",
    "summary": "Run heavy read-only reports on a replica (DSN from environment vars)",
    "category": "Tools",
    "author": "YourOrg",
    "license": "AGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
