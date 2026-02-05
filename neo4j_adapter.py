# neo4j_adapter.py
# Demo-safe stub (Neo4j disabled)

class Neo4jAdapter:
    def __init__(self):
        self.enabled = False

    def status(self):
        return {
            "neo4j": "disabled",
            "reason": "Demo mode – graph DB optional"
        }
