"""Hand the two drafts to an in-process loopback. No socket is opened."""

from __future__ import annotations

import sys

from scale_host.cloud_request import CloudRequest, preview_provider, text_request, vision_request


class LoopbackTransport:
    def __init__(self) -> None:
        self.bodies: list[dict[str, object]] = []

    def post(self, request: CloudRequest) -> dict[str, object]:
        self.bodies.append(request.model_dump())
        return {"received": True, "task": request.task}


def post_drafts(transport: LoopbackTransport, provider: str, image_path: str, label: str) -> None:
    transport.post(vision_request(provider, image_path))
    transport.post(text_request(label))


def main() -> None:
    transport = LoopbackTransport()
    post_drafts(transport, preview_provider(), "banana.jpg", "banana")
    vision, text = transport.bodies
    print(f"posted: {len(transport.bodies)}")
    print(f"vision_task: {vision['task']}")
    print(f"text_task: {text['task']}")
    print("remote: loopback")
    print("sent_to_internet: no")


if __name__ == "__main__":
    main()
    sys.exit(0)
