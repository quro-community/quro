"""
DeepScanner negative test fixture — intentional broken code patterns.

@module quro_cli.test_fixtures.deep_scanner_negative
@intent Provides files with structural issues that should trigger DeepScanner diagnostics.
"""

# Scenario 1: Dual-write pattern — multiple INSERT INTO in same file scope
# Should trigger DUAL_WRITE_PATTERN diagnostic.
class DataWriter:
    """Writes data to multiple tables."""

    def save_user(self, user_id: int, name: str):
        self.db.execute("INSERT INTO users (id, name) VALUES (user_id, name)")
        self.db.execute("INSERT INTO audit_log (action, user_id) VALUES ('created', user_id)")
        return user_id


# Scenario 2: Method references attributes that don't exist in AST
class BrokenClient:
    """A client with unbound attribute references."""

    def __init__(self):
        self.conn = None
        self.timeout = 30

    def fetch(self):
        result = self.conn.execute()
        return result

    def disconnect(self):
        self.conn.close()

    def reload(self):
        self.conn = None
        self.timeout = 60


# Scenario 3: Cross-class unbound attribute reference
# ConfigStore has 'host' and 'port' in AST.
# The test code below references ConfigStore.api_key — NOT in AST.
class ConfigStore:
    """Stores configuration values."""

    def __init__(self):
        self.host = "localhost"
        self.port = 5432

    def connect(self):
        return f"{self.host}:{self.port}"


class ServiceConsumer:
    """A consumer that references an unbound attribute on ConfigStore."""

    def __init__(self):
        self.store = ConfigStore()

    def read_config(self):
        val = ConfigStore.host
        ConfigStore.api_key
        ConfigStore.nonexistent_token
        return val
