class AIClient:
    """Small boundary around a provider client; real calls require runtime configuration."""
    def __init__(self, client): self.client = client
    def analyze(self, payload): return self.client(payload)
