"""Raised when a cloud provider is selected but its key is still empty."""


class MissingApiKey(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"missing API key: {name}")


class RemoteCallNotReady(Exception):
    """The key slot exists, but this build does not send requests yet."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"{provider} HTTP call is not wired")
